#!/usr/bin/env python3
"""
JIRA client for feedback knowledge updater.
Handles JIRA connections, ticket fetching, and child ticket caching.
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from jira import JIRA


class JiraClient:
    """JIRA client wrapper with caching and retry logic"""
    
    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.jira_client = None
        self._child_tickets_cache = {}
        
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize JIRA client connection"""
        try:
            self.jira_client = JIRA(
                server=self.config['jira']['server'],
                basic_auth=(self.config['jira']['username'], self.config['jira']['password']),
                options={'verify': self.config['jira']['verify']}
            )
            self.logger.info("JIRA client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize JIRA client: {e}")
            self.jira_client = None
            raise
    
    def build_jira_url(self, ticket_key: str) -> str:
        """Build JIRA URL for a ticket"""
        if self.config and self.config.get('jira', {}).get('server'):
            base_url = self.config['jira']['server'].rstrip('/')
            return f"{base_url}/browse/{ticket_key}"
        return f"https://jira.example.com/browse/{ticket_key}"  # Fallback
    
    def fetch_parent_tickets(self, sort_by_child_count: bool = False, limit: Optional[int] = None) -> List:
        """Fetch parent tickets from JIRA"""
        if not self.jira_client:
            self.logger.error("JIRA client not initialized")
            return []
        
        try:
            parent_query = self.config['jira']['parent_query']
            
            if sort_by_child_count:
                # Fetch all parent tickets across pages for accurate ranking
                self.logger.info("🔍 Fetching all parent tickets for ranking...")
                all_issues = []
                start_at = 0
                page_size = 100
                while True:
                    page = self.jira_client.search_issues(parent_query, startAt=start_at, maxResults=page_size)
                    all_issues.extend(page)
                    if len(page) < page_size:
                        break
                    start_at += page_size
                tickets = all_issues
            else:
                # Determine how many to fetch (buffer for limit or full page)
                if limit:
                    max_results = limit * 3
                else:
                    max_results = 1000
                tickets = self.jira_client.search_issues(parent_query, maxResults=max_results)
            
            self.logger.info(f"Found {len(tickets)} parent tickets from JIRA")
            
            # If sorting by child count, we need to fetch child counts
            if sort_by_child_count:
                # Clear child ticket cache to ensure fresh counts
                self.clear_child_ticket_cache()
                # Add total descendant count information to tickets
                for ticket in tickets:
                    all_descendants = self.get_total_descendants(ticket)
                    ticket.child_count = len(all_descendants)

                # Sort by total descendant count descending
                tickets = sorted(tickets, key=lambda t: getattr(t, 'child_count', 0), reverse=True)
                self.logger.info(f"Sorted tickets by total descendant count (highest first)")
            
            # Apply limit after sorting if specified
            if limit and len(tickets) > limit:
                tickets = tickets[:limit]
                self.logger.info(f"Limited to {limit} tickets")
            
            return tickets
            
        except Exception as e:
            self.logger.error(f"Error fetching parent tickets: {e}")
            return []
    
    def get_child_tickets(self, parent_ticket) -> List:
        """Get duplicate child tickets for a parent ticket with caching

        Only counts issues linked via the 'Duplicate' type inward links."""
        parent_key = parent_ticket.key

        # Check cache first
        if parent_key in self._child_tickets_cache:
            return self._child_tickets_cache[parent_key]
        if not self.jira_client:
            self.logger.error("JIRA client not initialized")
            return []
        try:
            child_tickets = []

            # Fetch full ticket with duplicate links
            full_ticket = self.jira_client.issue(parent_key, expand='issuelinks')

            # Add only inward duplicates
            if hasattr(full_ticket.fields, 'issuelinks'):
                for link in full_ticket.fields.issuelinks:
                    if 'duplicat' in link.type.name.lower() and hasattr(link, 'inwardIssue'):
                        child_tickets.append(link.inwardIssue)

            # Cache result
            self._child_tickets_cache[parent_key] = child_tickets
            self.logger.debug(f"Found {len(child_tickets)} duplicate child tickets for {parent_key}")
            return child_tickets
        except Exception as e:
            self.logger.error(f"Error fetching duplicate child tickets for {parent_key}: {e}")
            self._child_tickets_cache[parent_key] = []
            return []
    
    def get_total_descendants(self, parent_ticket) -> List:
        """Get all descendants (children, grandchildren, etc.) recursively
        
        This method counts all descendants in the hierarchy, not just direct children.
        """
        visited = set()
        all_descendants = []
        
        def collect_descendants(ticket):
            if ticket.key in visited:
                return  # Avoid infinite loops
            visited.add(ticket.key)
            
            # Get direct children
            direct_children = self.get_child_tickets(ticket)
            all_descendants.extend(direct_children)
            
            # Recursively get descendants of each child
            for child in direct_children:
                collect_descendants(child)
        
        collect_descendants(parent_ticket)
        return all_descendants
    
    def clear_child_ticket_cache(self) -> None:
        """Clear the child ticket cache"""
        self._child_tickets_cache.clear()
        self.logger.info("Child ticket cache cleared")
    
    def get_ticket_by_key(self, ticket_key: str):
        """Get a specific ticket by its key"""
        if not self.jira_client:
            self.logger.error("JIRA client not initialized")
            return None
        
        try:
            ticket = self.jira_client.issue(ticket_key)
            return ticket
        except Exception as e:
            self.logger.error(f"Error fetching ticket {ticket_key}: {e}")
            return None
    
    def is_connected(self) -> bool:
        """Check if JIRA client is connected and functional"""
        return self.jira_client is not None
    
    def test_connection(self) -> bool:
        """Test JIRA connection"""
        if not self.jira_client:
            return False
        
        try:
            # Try to fetch user info as a simple connection test
            user = self.jira_client.current_user()
            self.logger.info(f"JIRA connection test successful for user: {user}")
            return True
        except Exception as e:
            self.logger.error(f"JIRA connection test failed: {e}")
            return False
    
    def retry_api_call(self, func, *args, **kwargs):
        """Retry API calls with exponential backoff"""
        max_retries = 3
        delays = [1, 2, 4]
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"API call failed after {max_retries} attempts: {e}")
                    raise
                else:
                    self.logger.warning(f"API call attempt {attempt + 1} failed: {e}. Retrying in {delays[attempt]} seconds...")
                    time.sleep(delays[attempt]) 

    def has_duplicate_parent(self, ticket) -> bool:
        """Return True if this ticket duplicates another (has an outward 'Duplicate' link)"""
        key = ticket.key
        full_ticket = self.jira_client.issue(key, expand='issuelinks')
        if hasattr(full_ticket.fields, 'issuelinks'):
            for link in full_ticket.fields.issuelinks:
                if 'duplicat' in link.type.name.lower() and hasattr(link, 'outwardIssue'):
                    return True
        return False 