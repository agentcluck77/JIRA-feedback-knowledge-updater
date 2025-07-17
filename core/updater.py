#!/usr/bin/env python3
"""
Main updater class for feedback knowledge updater.
Orchestrates JIRA ticket processing, bot interactions, and knowledge base management.
"""

import os
import requests
import logging
import hashlib
import uuid
import time
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

from config.bot_config import merge_classifier_bot_configs, get_bot_type_display_name, get_summarizer_bot_config
from database.db_manager import DatabaseManager
from jira_integration.client import JiraClient
from bots.alpha_knowledge import AlphaKnowledgeClient
from bots.alpha_summarizer import AlphaSummarizerClient


class FeedbackKnowledgeUpdater:
    """Main updater class that orchestrates all operations"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger, selected_classifier_bot: Optional[str] = None, selected_summarizer_bot: str = 'default'):
        self.config = config
        self.logger = logger
        self.selected_classifier_bot = selected_classifier_bot
        self.selected_summarizer_bot = selected_summarizer_bot
        
        # Initialize components
        self.db_manager = DatabaseManager(logger=logger)
        self.jira_client = JiraClient(config, logger)
        self.alpha_client = None
        self.alpha_summarizer_client = None
        
        # Initialize secrets
        self._initialize_secrets()
        
        # Initialize Alpha Knowledge clients if needed
        self._initialize_alpha_client()
        self._initialize_alpha_summarizer_client()
    
    def _initialize_secrets(self) -> None:
        """Initialize bot secrets from environment variables and config files"""
        self.classifier_bot_app_secret = None
        
        # Get summarizer bot app secret from config or environment
        summarizer_config = self.config.get('summarizer_bot_api', {})
        self.summarizer_bot_app_secret = summarizer_config.get('app_secret') or os.getenv('SUMMARIZER_BOT_APP_SECRET')
        
        if self.selected_classifier_bot:
            bot_config = self._get_bot_config()
            if bot_config and bot_config.get('bot_type', 'ai_bot_platform') == 'ai_bot_platform':
                # Get app secret from bot config first, then environment
                self.classifier_bot_app_secret = bot_config.get('app_secret')
                if not self.classifier_bot_app_secret:
                    # Fallback to environment variables
                    bot_secret_var = f'CLASSIFIER_BOT_{self.selected_classifier_bot.upper()}_APP_SECRET'
                    self.classifier_bot_app_secret = os.getenv(bot_secret_var) or os.getenv('CLASSIFIER_BOT_APP_SECRET')
    
    def _initialize_alpha_client(self) -> None:
        """Initialize Alpha Knowledge classifier client if needed"""
        if self.selected_classifier_bot:
            bot_config = self._get_bot_config()
            if bot_config and bot_config.get('bot_type') == 'alpha_knowledge':
                try:
                    self.alpha_client = AlphaKnowledgeClient(bot_config, self.logger)
                    self.logger.info(f"Alpha Knowledge classifier client initialized for bot '{self.selected_classifier_bot}'")
                except Exception as e:
                    self.logger.error(f"Failed to initialize Alpha Knowledge classifier client for bot '{self.selected_classifier_bot}': {e}")
                    self.alpha_client = None
    
    def _initialize_alpha_summarizer_client(self) -> None:
        """Initialize Alpha Knowledge summarizer client if needed"""
        summarizer_config = get_summarizer_bot_config(self.selected_summarizer_bot)
        if summarizer_config and summarizer_config.get('bot_type') == 'alpha_knowledge':
            try:
                self.alpha_summarizer_client = AlphaSummarizerClient(summarizer_config, self.logger)
                self.logger.info(f"Alpha Knowledge summarizer client initialized for bot '{self.selected_summarizer_bot}'")
            except Exception as e:
                self.logger.error(f"Failed to initialize Alpha Knowledge summarizer client for bot '{self.selected_summarizer_bot}': {e}")
                self.alpha_summarizer_client = None
    
    def _get_bot_config(self) -> Optional[Dict[str, Any]]:
        """Get configuration for the selected classifier bot"""
        if not self.selected_classifier_bot:
            return None
        
        merged_config = merge_classifier_bot_configs()
        return merged_config.get(self.selected_classifier_bot)
    
    def _get_bot_type(self) -> str:
        """Get the bot type for the selected classifier bot"""
        bot_config = self._get_bot_config()
        if bot_config:
            return bot_config.get('bot_type', 'ai_bot_platform')
        return 'ai_bot_platform'  # Default fallback
    
    def get_existing_tickets(self) -> Dict[str, Dict]:
        """Get all existing tickets from database"""
        return self.db_manager.get_existing_tickets()
    
    def fetch_parent_tickets(self, sort_by_child_count: bool = False, limit: Optional[int] = None) -> List:
        """Fetch parent tickets from JIRA"""
        return self.jira_client.fetch_parent_tickets(sort_by_child_count, limit)
    
    def get_child_tickets(self, parent_ticket) -> List:
        """Get child tickets for a parent ticket"""
        return self.jira_client.get_child_tickets(parent_ticket)
    
    def get_total_descendants(self, parent_ticket) -> List:
        """Get all descendants (children, grandchildren, etc.) recursively"""
        return self.jira_client.get_total_descendants(parent_ticket)
    
    def clear_child_ticket_cache(self) -> None:
        """Clear child ticket cache"""
        self.jira_client.clear_child_ticket_cache()
        self.db_manager.clear_child_ticket_cache()
    
    def send_bot_request(self, ticket_key: str, prompt_content: str) -> Tuple[bool, Optional[str]]:
        """Send request to summarizer bot"""
        # Get summarizer bot configuration
        summarizer_config = get_summarizer_bot_config(self.selected_summarizer_bot)
        if not summarizer_config:
            self.logger.warning(f"Summarizer bot '{self.selected_summarizer_bot}' not configured, using fallback mode")
            return self.simulate_bot_response(prompt_content, ticket_key)
        
        bot_type = summarizer_config.get('bot_type', 'ai_bot_platform')
        
        if bot_type == 'alpha_knowledge':
            return self._send_alpha_knowledge_summarizer_request(ticket_key, prompt_content, summarizer_config)
        else:
            return self._send_ai_bot_platform_summarizer_request(ticket_key, prompt_content, summarizer_config)
    
    def _send_alpha_knowledge_summarizer_request(self, ticket_key: str, prompt_content: str, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Send request to Alpha Knowledge summarizer"""
        if not self.alpha_summarizer_client:
            self.logger.error(f"Alpha Knowledge summarizer client not initialized for bot '{self.selected_summarizer_bot}'")
            return False, None
        
        try:
            # Use a user email from config or fallback
            user_email = config.get('user_email', 'system@example.com')
            success, response = self.alpha_summarizer_client.send_summarization_request(prompt_content, user_email)
            
            if success and response:
                self.logger.info(f"Received Alpha Knowledge summarizer response for {ticket_key}")
                return True, response
            else:
                self.logger.warning(f"Failed to get response from Alpha Knowledge summarizer for {ticket_key}")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error sending Alpha Knowledge summarizer request for {ticket_key}: {e}")
            return False, None
    
    def _send_ai_bot_platform_summarizer_request(self, ticket_key: str, prompt_content: str, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Send request to AI Bot Platform summarizer"""
        app_secret = config.get('app_secret') or self.summarizer_bot_app_secret
        if not app_secret:
            self.logger.warning("AI Bot Platform summarizer app secret not configured, using fallback mode")
            return self.simulate_bot_response(prompt_content, ticket_key)
        
        try:
            request_id = str(uuid.uuid4())
            
            # Prepare request data
            request_data = {
                'app_id': config['app_id'],
                'user_email': config['user_email'],
                'app_secret': app_secret,
                'request_id': request_id,
                'question': prompt_content
            }
            
            # Send request
            response = requests.post(
                config['url'],
                json=request_data,
                timeout=30
            )
            
            if response.status_code == 200:
                response_data = response.json()
                bot_response = response_data.get('reply', '').strip()
                
                if bot_response:
                    self.logger.info(f"Received AI Bot Platform summarizer response for {ticket_key}")
                    return True, bot_response
                else:
                    self.logger.warning(f"Empty response from AI Bot Platform summarizer for {ticket_key}")
                    return False, None
            else:
                self.logger.error(f"AI Bot Platform summarizer request failed with status {response.status_code}: {response.text}")
                return False, None
                
        except Exception as e:
            self.logger.error(f"Error sending AI Bot Platform summarizer request for {ticket_key}: {e}")
            return False, None
    
    def simulate_bot_response(self, request_content: str, ticket_key: str) -> Tuple[bool, str]:
        """Simulate bot response when app secret is not available"""
        self.logger.info(f"SIMULATION MODE: Generating simulated response for {ticket_key}")
        
        # Create a simulated response based on the content
        lines = request_content.split('\n')
        parent_summary = ""
        child_summaries = []
        
        for line in lines:
            if line.startswith("Parent Ticket Summary:"):
                parent_summary = line.replace("Parent Ticket Summary:", "").strip()
            elif line.startswith("Child ") and "Summary:" in line:
                child_summaries.append(line.split("Summary:", 1)[1].strip())
        
        simulated_response = f"Summary: {parent_summary}\n\n"
        if child_summaries:
            simulated_response += "Key Issues:\n"
            for i, child_summary in enumerate(child_summaries[:3], 1):
                simulated_response += f"{i}. {child_summary}\n"
        
        simulated_response += f"\nThis is a simulated response generated for testing purposes."
        
        return True, simulated_response
    
    def send_classifier_command(self, command: str, ticket_key: str = None) -> Tuple[bool, Optional[Dict]]:
        """Send command to classifier bot"""
        bot_config = self._get_bot_config()
        if not bot_config:
            return False, {'error': 'No bot configuration found'}
        
        bot_type = bot_config.get('bot_type', 'ai_bot_platform')
        
        if bot_type == 'ai_bot_platform':
            return self._send_ai_bot_platform_command(command, ticket_key, bot_config)
        elif bot_type == 'alpha_knowledge':
            return self._send_alpha_knowledge_command(command, ticket_key)
        else:
            return False, {'error': f'Unsupported bot type: {bot_type}'}
    
    def _send_ai_bot_platform_command(self, command: str, ticket_key: str, bot_config: Dict) -> Tuple[bool, Optional[Dict]]:
        """Send command to AI Bot Platform"""
        try:
            request_data = {
                'app_id': bot_config['app_id'],
                'user_email': bot_config['user_email'],
                'app_secret': bot_config.get('app_secret') or self.classifier_bot_app_secret,
                'message_content': command
            }
            
            response = requests.post(bot_config['url'], json=request_data, timeout=30)
            
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {'error': f'HTTP {response.status_code}: {response.text}'}
                
        except Exception as e:
            return False, {'error': str(e)}
    
    def _send_alpha_knowledge_command(self, command: str, ticket_key: str) -> Tuple[bool, Optional[Dict]]:
        """Send command to Alpha Knowledge"""
        if not self.alpha_client:
            return False, {'error': 'Alpha Knowledge client not initialized'}
        
        # Parse command for Alpha Knowledge operations
        if command.startswith('add:'):
            content = command[4:].strip()
            citation_url = self.jira_client.build_jira_url(ticket_key)
            citation_title = f"JIRA Ticket {ticket_key}"
            
            knowledge_id = self.alpha_client.upload_knowledge(content, citation_url, citation_title, ticket_key)
            if knowledge_id:
                return True, {'knowledge_id': knowledge_id}
            else:
                return False, {'error': 'Failed to upload knowledge'}
        
        elif command.startswith('delete:'):
            try:
                knowledge_id = int(command[7:].strip())
                success = self.alpha_client.delete_knowledge(knowledge_id)
                if success:
                    return True, {'status': 'deleted'}
                else:
                    return False, {'error': 'Failed to delete knowledge'}
            except ValueError:
                return False, {'error': 'Invalid knowledge ID format'}
        
        elif command == 'list':
            result = self.alpha_client.list_knowledge()
            if result:
                return True, result
            else:
                return False, {'error': 'Failed to list knowledge'}
        
        else:
            return False, {'error': f'Unsupported Alpha Knowledge command: {command}'}
    
    def get_classifier_submissions(self) -> Dict[str, Dict]:
        """Get all classifier bot submissions"""
        return self.db_manager.get_classifier_submissions()
    
    def record_classifier_submission(self, ticket_key: str, summary_text: str, action_type: str = 'add', 
                                   doc_id: str = None, alpha_knowledge_id: int = None) -> None:
        """Record classifier bot submission"""
        if not self.selected_classifier_bot:
            return
        
        bot_type = self._get_bot_type()
        self.db_manager.record_classifier_submission(
            ticket_key, self.selected_classifier_bot, summary_text, 
            action_type, doc_id, alpha_knowledge_id, bot_type
        )
    
    def sync_summaries_with_classifier(self, init_mode: bool = False, processed_ticket_keys=None) -> None:
        """Sync summaries with classifier bot"""
        # Get tickets to sync
        if processed_ticket_keys:
            # Only sync specific tickets
            existing_tickets = self.get_existing_tickets()
            tickets_data = {}
            for ticket_key in processed_ticket_keys:
                if ticket_key in existing_tickets:
                    tickets_data[ticket_key] = existing_tickets[ticket_key]['summary']
        else:
            # Sync all tickets
            existing_tickets = self.get_existing_tickets()
            tickets_data = {key: data['summary'] for key, data in existing_tickets.items() if data.get('summary')}
        
        if tickets_data:
            self.sync_with_classifier_bot(tickets_data, init_mode)
        else:
            self.logger.info("No tickets to sync with classifier bot")

    def sync_with_classifier_bot(self, tickets_data: Dict[str, str], init_mode: bool = False) -> None:
        """Sync tickets with classifier bot"""
        if not self.selected_classifier_bot:
            self.logger.warning("No classifier bot selected for sync")
            return
        
        bot_type = self._get_bot_type()
        existing_submissions = self.get_classifier_submissions()
        
        for ticket_key, summary in tickets_data.items():
            submission_key = f"{ticket_key}:{self.selected_classifier_bot}"
            existing_entry = existing_submissions.get(submission_key)
            
            if bot_type == 'ai_bot_platform':
                if existing_entry:
                    self._handle_ai_bot_platform_update(ticket_key, summary, existing_entry)
                else:
                    self._handle_ai_bot_platform_add(ticket_key, summary)
            
            elif bot_type == 'alpha_knowledge':
                if existing_entry:
                    self._handle_alpha_knowledge_update(ticket_key, summary, existing_entry)
                else:
                    self._handle_alpha_knowledge_add(ticket_key, summary)
    
    def _handle_ai_bot_platform_add(self, ticket_key: str, summary: str) -> bool:
        """Handle adding to AI Bot Platform"""
        command = f"add: {self.clean_summary_for_classifier(summary)}"
        success, response = self.send_classifier_command(command, ticket_key)
        
        if success:
            doc_id = self.extract_doc_id_from_response(response)
            self.record_classifier_submission(ticket_key, summary, 'add', doc_id)
            return True
        
        return False
    
    def _handle_ai_bot_platform_update(self, ticket_key: str, summary: str, existing_entry: Dict) -> bool:
        """Handle updating AI Bot Platform entry"""
        current_hash = hashlib.sha256(summary.encode('utf-8')).hexdigest()
        
        if current_hash != existing_entry.get('summary_hash'):
            command = f"update: {self.clean_summary_for_classifier(summary)}"
            success, response = self.send_classifier_command(command, ticket_key)
            
            if success:
                doc_id = self.extract_doc_id_from_response(response) or existing_entry.get('doc_id')
                self.record_classifier_submission(ticket_key, summary, 'update', doc_id)
                return True
        
        return False
    
    def _handle_alpha_knowledge_add(self, ticket_key: str, summary: str) -> bool:
        """Handle adding to Alpha Knowledge"""
        command = f"add: {self.clean_summary_for_classifier(summary)}"
        success, response = self.send_classifier_command(command, ticket_key)
        
        if success:
            knowledge_id = self._extract_alpha_knowledge_id_from_response(response)
            self.record_classifier_submission(ticket_key, summary, 'add', alpha_knowledge_id=knowledge_id)
            return True
        
        return False
    
    def _handle_alpha_knowledge_update(self, ticket_key: str, summary: str, existing_entry: Dict) -> bool:
        """Handle updating Alpha Knowledge entry"""
        current_hash = hashlib.sha256(summary.encode('utf-8')).hexdigest()
        
        if current_hash != existing_entry.get('summary_hash'):
            # For Alpha Knowledge, we delete and re-add for updates
            if existing_entry.get('alpha_knowledge_id'):
                delete_command = f"delete: {existing_entry['alpha_knowledge_id']}"
                self.send_classifier_command(delete_command, ticket_key)
            
            # Add new version
            return self._handle_alpha_knowledge_add(ticket_key, summary)
        
        return False
    
    def _extract_alpha_knowledge_id_from_response(self, response_data: Dict) -> Optional[int]:
        """Extract Alpha Knowledge knowledge ID from response"""
        if isinstance(response_data, dict):
            return response_data.get('knowledge_id')
        return None
    
    def extract_doc_id_from_response(self, response_data: Dict) -> Optional[str]:
        """Extract document ID from AI Bot Platform response"""
        if isinstance(response_data, dict):
            return response_data.get('doc_id') or response_data.get('document_id')
        return None
    
    def clean_summary_for_classifier(self, summary: str) -> str:
        """Clean summary text for classifier bot"""
        # Remove excessive whitespace
        cleaned = ' '.join(summary.split())
        
        # Remove markdown-style formatting
        cleaned = cleaned.replace('**', '').replace('*', '').replace('`', '')
        
        # Limit length
        if len(cleaned) > 2000:
            cleaned = cleaned[:1997] + '...'
        
        return cleaned
    
    def generate_ai_summary(self, ticket) -> Optional[str]:
        """Generate AI summary for a ticket"""
        try:
            # Build prompt content
            prompt_parts = [f"Parent Ticket Summary: {ticket.fields.summary}"]
            # Prevent cycles in descendant traversal
            visited = set()
            visited.add(ticket.key)
            
            # Add descendant ticket information recursively
            def add_descendants(parent_ticket, level=1):
                descendants = self.get_child_tickets(parent_ticket)
                for i, desc in enumerate(descendants, 1):
                    if desc.key in visited:
                        continue
                    visited.add(desc.key)
                    # Determine prefix based on level
                    if level == 1:
                        prefix = "Child"
                    elif level == 2:
                        prefix = "Grandchild"
                    else:
                        prefix = "Great-" * (level - 2) + "Grandchild"
                    prompt_parts.append(f"{prefix} {i} Summary: {desc.fields.summary}")
                    add_descendants(desc, level + 1)
            add_descendants(ticket)
            prompt_content = "\n".join(prompt_parts)
            self.logger.debug(f"Summarization prompt for {ticket.key}:\n{prompt_content}")
            
            # Attempt summarization with retry
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                success, response = self.send_bot_request(ticket.key, prompt_content)
                if success and response:
                    return response.strip()
                self.logger.warning(f"Summarization attempt {attempt}/{max_retries} failed for {ticket.key}")
                if attempt < max_retries:
                    time.sleep(2 ** (attempt - 1))  # exponential backoff: 1s,2s,4s
            self.logger.error(f"All {max_retries} summarization attempts failed for {ticket.key}; falling back to raw parent summary")
            return ticket.fields.summary
        except Exception as e:
            self.logger.error(f"Error in generate_ai_summary for {ticket.key}: {e}")
            # Fallback to raw summary on error
            try:
                return ticket.fields.summary
            except:
                return None
    
    def save_ticket_to_database(self, ticket_key: str, summary: str, child_tickets=None, bot_request_id=None) -> None:
        """Save ticket to database"""
        self.db_manager.save_ticket_to_database(ticket_key, summary, child_tickets, bot_request_id)
    
    def identify_tickets_to_process(self, all_tickets: List, existing_tickets: Dict, 
                                   force_refresh: bool = False) -> Tuple[List, List]:
        """Identify which tickets need processing"""
        tickets_to_process = []
        tickets_to_update = []
        
        for ticket in all_tickets:
            ticket_key = ticket.key
            
            if ticket_key in existing_tickets:
                if force_refresh:
                    tickets_to_update.append(ticket)
                else:
                    # Refresh if previous summary was raw parent summary (fallback)
                    stored_summary = existing_tickets[ticket_key].get('summary', '')
                    raw_summary = ticket.fields.summary
                    if stored_summary == raw_summary:
                        tickets_to_update.append(ticket)
                        continue
                    # Check if descendant count changed
                    all_descendants = self.get_total_descendants(ticket)
                    current_descendant_count = len(all_descendants)
                    stored_descendant_count = existing_tickets[ticket_key].get('child_count', 0)
                    if current_descendant_count != stored_descendant_count:
                        tickets_to_update.append(ticket)
            else:
                tickets_to_process.append(ticket)
        
        return tickets_to_process, tickets_to_update
    
    def process_tickets(self, tickets: List, ticket_type: str = "tickets") -> Dict[str, int]:
        """Process a list of tickets"""
        processed_count = 0
        failed_count = 0
        
        for i, ticket in enumerate(tickets, 1):
            try:
                self.logger.info(f"Processing {ticket_type} {i}/{len(tickets)}: {ticket.key}")
                
                # Generate AI summary
                summary = self.generate_ai_summary(ticket)
                
                if summary:
                    # Save to database
                    all_descendants = self.get_total_descendants(ticket)
                    self.save_ticket_to_database(ticket.key, summary, all_descendants)
                    processed_count += 1
                    
                    self.logger.info(f"Successfully processed {ticket.key}")
                else:
                    failed_count += 1
                    self.logger.warning(f"Failed to generate summary for {ticket.key}")
                    
            except Exception as e:
                failed_count += 1
                self.logger.error(f"Error processing {ticket.key}: {e}")
        
        return {'processed': processed_count, 'failed': failed_count}
    
    def run_update(self, init_mode: bool = False, force_refresh: bool = False, 
                  limit_tickets: Optional[int] = None, resize_tickets: Optional[int] = None,
                  report_only_processed: bool = True) -> Dict[str, Any]:
        """Run the main update process"""
        start_time = datetime.now()
        
        try:
            if init_mode:
                self.logger.info("Starting INITIALIZATION mode - processing tickets prioritized by total descendant count")
                # Only purge entries for the selected bot
                all_subs = self.get_classifier_submissions()
                to_purge = [e['ticket_key'] for e in all_subs.values()
                            if e.get('bot_name') == self.selected_classifier_bot and e.get('ticket_key')]
                if to_purge:
                    self.logger.info(f"INIT MODE: Purging {len(to_purge)} entries from remote classifier bot '{self.selected_classifier_bot}'")
                    for ticket_key in to_purge:
                        self._remove_ticket_from_classifier(ticket_key)
                # Clear local database for a fresh initialization
                if self.selected_classifier_bot:
                    self.logger.info(f"INIT MODE: Clearing local ticket_index and classifier submissions for bot '{self.selected_classifier_bot}'")
                    cursor = self.db_manager.db_connection.cursor()
                    # Clear all processed tickets
                    cursor.execute("DELETE FROM ticket_index")
                    # Clear child ticket cache
                    cursor.execute("DELETE FROM child_tickets")
                    # Clear local classifier submissions for this bot
                    cursor.execute("DELETE FROM classifier_bot_submissions WHERE bot_name = ?", (self.selected_classifier_bot,))
                    self.db_manager.db_connection.commit()
                # Post-initialization processing: fetch and process tickets for INIT mode
                existing_tickets = self.get_existing_tickets()
                all_tickets = self.fetch_parent_tickets(True, limit_tickets)
                # Filter to ultimate parent tickets only (no duplicate parent links)
                all_tickets = [t for t in all_tickets if not self.jira_client.has_duplicate_parent(t)]
                self.logger.info(f"Filtered to {len(all_tickets)} ultimate parent tickets")
                if not all_tickets:
                    self.logger.warning("No tickets found")
                    return self._generate_empty_report()
                new_tickets, updated_tickets = self.identify_tickets_to_process(
                    all_tickets, existing_tickets, force_refresh
                )
                new_results = self.process_tickets(new_tickets, "new tickets")
                update_results = self.process_tickets(updated_tickets, "updated tickets")
                if self.selected_classifier_bot:
                    self.logger.info("🔄 INIT SYNC: Pushing all summaries to classifier bot")
                    self.sync_summaries_with_classifier(init_mode=True)
                duration = datetime.now() - start_time
                return {
                    'total_tickets': len(all_tickets),
                    'new_processed': new_results['processed'],
                    'updated_processed': update_results['processed'],
                    'total_processed': new_results['processed'] + update_results['processed'],
                    'total_failed': new_results['failed'] + update_results['failed'],
                    'duration': str(duration),
                }
            else:
                self.logger.info("Starting UPDATE mode - processing new/changed tickets only")
            
            # Handle explicit resize mode request
            existing_tickets = self.get_existing_tickets()
            if resize_tickets is not None and self.selected_classifier_bot:
                return self._handle_resize_mode(resize_tickets, existing_tickets, start_time, report_only_processed)
            
            # UPDATE mode with a classifier bot: enforce top-N and refresh summaries
            if not init_mode and self.selected_classifier_bot:
                existing_tickets = self.get_existing_tickets()
                existing_subs = self.get_classifier_submissions()
                current_N = len([e for e in existing_subs.values() if e.get('bot_name') == self.selected_classifier_bot])
                
                # Use limit_tickets if provided, otherwise use current_N
                target_N = limit_tickets if limit_tickets is not None else current_N
                
                if limit_tickets is not None:
                    self.logger.info(f"🔧 UPDATE-EXPANSION MODE: Classifier bot '{self.selected_classifier_bot}' has {current_N} tickets; expanding to {target_N}")
                else:
                    self.logger.info(f"🔧 UPDATE-RESIZE MODE: Classifier bot '{self.selected_classifier_bot}' has {current_N} tickets; enforcing top {current_N}")
                
                # Fetch fresh JIRA tickets sorted by total descendant count
                all_tickets = self.fetch_parent_tickets(sort_by_child_count=True)
                # Filter to ultimate parent tickets only (no duplicate parent links)
                all_tickets = [t for t in all_tickets if not self.jira_client.has_duplicate_parent(t)]
                self.logger.info(f"Filtered to {len(all_tickets)} ultimate parent tickets")
                # Determine top N tickets
                top_tickets = all_tickets[:target_N] if len(all_tickets) >= target_N else all_tickets
                target_keys = {t.key for t in top_tickets}
                # Identify submissions for this bot
                bot_submissions = [e for e in existing_subs.values() if e.get('bot_name') == self.selected_classifier_bot]
                # Determine which existing tickets (by ticket_key) should be removed (outside top N)
                # Only remove tickets if we're not in expansion mode
                removed_count = 0
                if limit_tickets is None:  # Only remove when not expanding
                    to_remove_keys = [entry['ticket_key'] for entry in bot_submissions if entry['ticket_key'] not in target_keys]
                    for ticket_key in to_remove_keys:
                        if self._remove_ticket_from_classifier(ticket_key):
                            removed_count += 1
                # Determine which top tickets are new to the classifier (not in bot_submissions)
                existing_bot_keys = {entry['ticket_key'] for entry in bot_submissions}
                to_add = [t for t in top_tickets if t.key not in existing_bot_keys]
                # Identify tickets that remain in top N and need refreshing (descendant count changed or force_refresh)
                to_update = []
                for ticket in top_tickets:
                    if ticket.key in existing_bot_keys:
                        if force_refresh or len(self.get_total_descendants(ticket)) != existing_tickets.get(ticket.key, {}).get('child_count', 0):
                            to_update.append(ticket)
                # Process additions and updates
                add_results = self.process_tickets(to_add, "new tickets")
                update_results = self.process_tickets(to_update, "updated tickets")
                # Sync processed tickets to classifier bot
                processed_keys = [t.key for t in to_add + to_update]
                if processed_keys:
                    self.logger.info(f"🔄 UPDATE SYNC: Syncing {len(processed_keys)} tickets to classifier bot")
                    self.sync_summaries_with_classifier(init_mode=False, processed_ticket_keys=processed_keys)
                # Build and return report
                duration = datetime.now() - start_time
                return {
                    'total_tickets': len(all_tickets),
                    'new_processed': add_results['processed'],
                    'updated_processed': update_results['processed'],
                    'total_processed': add_results['processed'] + update_results['processed'],
                    'total_failed': add_results['failed'] + update_results['failed'],
                    'duration': str(duration),
                    'resize_mode': True,
                    'resize_added': add_results['processed'],
                    'resize_removed': removed_count
                }
            # Fallback default update logic (no classifier bot or init_mode)
            existing_tickets = self.get_existing_tickets()
            all_tickets = self.fetch_parent_tickets(sort_by_child_count=False, limit=limit_tickets)
            # Filter to ultimate parent tickets only (no duplicate parent links)
            all_tickets = [t for t in all_tickets if not self.jira_client.has_duplicate_parent(t)]
            self.logger.info(f"Filtered to {len(all_tickets)} ultimate parent tickets")
            if not all_tickets:
                self.logger.warning("No tickets found")
                return self._generate_empty_report()
            new_tickets, updated_tickets = self.identify_tickets_to_process(all_tickets, existing_tickets, force_refresh)
            new_results = self.process_tickets(new_tickets, "new tickets")
            update_results = self.process_tickets(updated_tickets, "updated tickets")
            duration = datetime.now() - start_time
            return {
                'total_tickets': len(all_tickets),
                'new_processed': new_results['processed'],
                'updated_processed': update_results['processed'],
                'total_processed': new_results['processed'] + update_results['processed'],
                'total_failed': new_results['failed'] + update_results['failed'],
                'duration': str(duration),
            }
        except Exception as e:
            self.logger.error(f"Error in run_update: {e}")
            raise

    def _handle_resize_mode(self, target_count: int, existing_tickets: Dict, start_time: datetime, 
                           report_only_processed: bool) -> Dict[str, Any]:
        """Handle resize mode operations"""
        # Get current classifier bot ticket count
        existing_submissions = self.get_classifier_submissions()
        current_tickets = set()
        
        # Filter submissions for the selected bot
        for submission_key, submission in existing_submissions.items():
            if submission['bot_name'] == self.selected_classifier_bot:
                current_tickets.add(submission['ticket_key'])
        
        current_count = len(current_tickets)
        
        self.logger.info(f"🔧 RESIZE MODE: Classifier bot '{self.selected_classifier_bot}' has {current_count} tickets, target is {target_count}")
        
        if current_count == target_count:
            self.logger.info(f"✅ Already at target size of {target_count} tickets")
            return self._generate_resize_report(start_time, 0, 0, 0, target_count, current_count)
        
        # Fetch JIRA tickets and compute true top-N by child count
        self.logger.info("🔍 Fetching all parent tickets for ranking...")
        all_jira = self.fetch_parent_tickets(sort_by_child_count=True)
        # Filter to ultimate parent tickets only (no duplicate parent links)
        all_jira = [t for t in all_jira if not self.jira_client.has_duplicate_parent(t)]
        self.logger.info(f"Filtered to {len(all_jira)} ultimate parent tickets")
        target_tickets = all_jira[:target_count] if len(all_jira) >= target_count else all_jira
        target_ticket_keys = {t.key for t in target_tickets}
        self.logger.info(f"📊 Actual top {len(target_ticket_keys)} tickets by total descendant count from JIRA:")
        for i, ticket in enumerate(target_tickets[:5], 1):
            descendant_cnt = len(self.get_total_descendants(ticket))
            in_class = "✅" if ticket.key in current_tickets else "❌"
            self.logger.info(f"    {i:2d}. {ticket.key} ({descendant_cnt} total descendants) {in_class}")
        if len(target_tickets) > 5:
            self.logger.info(f"    ... and {len(target_tickets) - 5} more")

        # Find tickets that should be in classifier but aren't
        missing_from_classifier = []
        for ticket in target_tickets:
            if ticket.key not in current_tickets:
                missing_from_classifier.append(ticket)
        
        # Find tickets that are in classifier but shouldn't be (outside top N)
        tickets_to_remove = []
        for ticket_key in current_tickets:
            if ticket_key not in target_ticket_keys:
                tickets_to_remove.append(ticket_key)
        
        self.logger.info(f"📊 RESIZE analysis:")
        self.logger.info(f"   Target: top {target_count} tickets by total descendant count")
        self.logger.info(f"   Currently in classifier: {current_count} tickets")
        self.logger.info(f"   Need to add: {len(missing_from_classifier)} tickets")
        self.logger.info(f"   Need to remove: {len(tickets_to_remove)} tickets (outside top {target_count})")
        
        # Remove tickets that shouldn't be in the top N
        removed_count = 0
        if tickets_to_remove:
            self.logger.info(f"🗑️ Removing {len(tickets_to_remove)} tickets from classifier bot (outside top {target_count})")
            for ticket_key in tickets_to_remove:
                if self._remove_ticket_from_classifier(ticket_key):
                    removed_count += 1
                    
        # Process missing tickets as "new tickets" (already have ticket objects)
        new_tickets = missing_from_classifier
        
        if new_tickets:
            self.logger.info(f"📋 Will add {len(new_tickets)} tickets to ensure top {target_count}:")
            for i, ticket in enumerate(new_tickets[:10], 1):  # Show first 10
                # Use JIRA-derived child_count if available, otherwise fetch total descendants dynamically
                descendant_count = getattr(ticket, 'child_count', None)
                if descendant_count is None:
                    descendant_count = len(self.get_total_descendants(ticket))
                self.logger.info(f"    {i}. {ticket.key} ({descendant_count} total descendants)")
            if len(new_tickets) > 10:
                self.logger.info(f"    ... and {len(new_tickets) - 10} more tickets")
        elif removed_count > 0:
            self.logger.info(f"✅ Classifier bot resize complete: removed {removed_count} lower-priority tickets")
        else:
            self.logger.info(f"✅ Classifier bot already has the correct top {target_count} tickets")
        
        # No additional tickets to process - use the same flow as original
        updated_tickets = []  # No regular updates in resize mode
        
        # Process missing tickets as "new tickets"  
        resize_results = {'processed': 0, 'failed': 0}
        if new_tickets:
            self.logger.info(f"Found {len(new_tickets)} tickets to add for resize and {len(updated_tickets)} existing tickets to update")
            resize_results = self.process_tickets(new_tickets, "resize tickets")
        else:
            self.logger.info("No resize tickets to process")
        
        # Check if classifier already has correct tickets
        if not new_tickets and removed_count == 0:
            self.logger.info(f"✅ Classifier bot already has the correct top {target_count} tickets")
        
        # Sync processed tickets with classifier bot
        total_processed = resize_results['processed']
        if total_processed > 0:
            self.logger.info(f"Syncing {resize_results['processed']} resized tickets with classifier bot")
            # Sync summaries will handle the classifier bot integration
            processed_keys = [ticket.key for ticket in new_tickets[:resize_results['processed']]]
            self.sync_summaries_with_classifier(init_mode=False, processed_ticket_keys=processed_keys)
        elif removed_count > 0:
            self.logger.info(f"✅ Resize operation complete: removed {removed_count} tickets to optimize classifier bot")
        
        # Final count
        final_count = current_count - removed_count + resize_results['processed']
        
        # Log completion
        if resize_results['processed'] > 0 or removed_count > 0:
            self.logger.info(f"🎉 RESIZE COMPLETED: Database changed from {current_count} to {final_count} tickets")
            if final_count >= target_count:
                self.logger.info(f"✅ Target of {target_count} tickets reached!")
            else:
                remaining = target_count - final_count
                self.logger.info(f"📊 Still need {remaining} more tickets to reach target of {target_count}")
        
        # Build resize report and include removed count
        report = self._generate_resize_report(start_time, resize_results['processed'], 0, 
                                              resize_results['failed'], target_count, final_count)
        report['resize_removed'] = removed_count
        return report

    def _remove_ticket_from_classifier(self, ticket_key: str) -> bool:
        """Remove a ticket from the classifier bot"""
        self.logger.info(f"   Removing {ticket_key} from classifier bot")
        
        # Get submission details
        existing_submissions = self.get_classifier_submissions()
        submission_key = f"{ticket_key}:{self.selected_classifier_bot}"
        submission = existing_submissions.get(submission_key)
        
        if not submission:
            self.logger.warning(f"   ❌ No submission record found for {ticket_key}")
            return False
        
        bot_type = submission.get('bot_type', 'ai_bot_platform')
        
        try:
            if bot_type == 'alpha_knowledge':
                # Use Alpha Knowledge delete
                alpha_knowledge_id = submission.get('alpha_knowledge_id')
                self.logger.info(f"DEBUG: Retrieved alpha_knowledge_id = {alpha_knowledge_id}, type = {type(alpha_knowledge_id)}")
                if not alpha_knowledge_id:
                    self.logger.error(f"Invalid knowledge ID for Alpha Knowledge delete: {alpha_knowledge_id}")
                    self.logger.error(f"DEBUG: Full submission data: {submission}")
                    # Since we can't delete from the API, just remove from our database
                    success = self._remove_submission_from_database(ticket_key)
                    if success:
                        self.logger.warning(f"   ❌ Failed to remove {ticket_key} from classifier bot, but removed from database")
                        return False
                    else:
                        self.logger.warning(f"   ❌ Failed to remove {ticket_key} from both classifier and database")
                        return False
                
                self.logger.info(f"Deleting Alpha Knowledge knowledge entry {alpha_knowledge_id}")
                success = self.alpha_client.delete_knowledge(alpha_knowledge_id)
                if success:
                    self.logger.info(f"Successfully deleted knowledge entry {alpha_knowledge_id}")
                    # Remove from database
                    self._remove_submission_from_database(ticket_key)
                    self.logger.info(f"   ✅ Successfully removed {ticket_key} from classifier bot")
                    return True
                else:
                    self.logger.warning(f"Failed to delete knowledge entry {alpha_knowledge_id}")
                    # Try to remove from database anyway since it might be a stale entry
                    self._remove_submission_from_database(ticket_key)
                    self.logger.warning(f"   ❌ Failed to remove {ticket_key} from classifier bot")
                    return False
                    
            else:
                # Use AI Bot Platform delete
                doc_id = submission.get('doc_id')
                if not doc_id:
                    self.logger.warning(f"   ❌ No doc_id found for {ticket_key}")
                    # Remove from database anyway since it's incomplete
                    self._remove_submission_from_database(ticket_key)
                    return False
                
                command = f"delete: {doc_id}"
                success, response = self.send_classifier_command(command, ticket_key)
                if success:
                    # Remove from database
                    self._remove_submission_from_database(ticket_key)
                    self.logger.info(f"   ✅ Successfully removed {ticket_key} from classifier bot")
                    return True
                else:
                    # Try to remove from database anyway since deletion failed
                    self._remove_submission_from_database(ticket_key)
                    self.logger.warning(f"   ❌ Failed to remove {ticket_key} from classifier bot")
                    return False
                    
        except Exception as e:
            self.logger.error(f"   ❌ Error removing {ticket_key}: {e}")
            # Try to clean up database entry anyway
            self._remove_submission_from_database(ticket_key)
            return False

    def _remove_submission_from_database(self, ticket_key: str) -> bool:
        """Remove a submission from the database"""
        try:
            # Use direct database access since we need to delete the entry
            if hasattr(self.db_manager, 'db_connection') and self.db_manager.db_connection:
                db_query = self.db_manager.db_connection.cursor()
                db_query.execute("""
                    DELETE FROM classifier_bot_submissions 
                    WHERE ticket_key = ? AND bot_name = ?
                """, (ticket_key, self.selected_classifier_bot))
                self.db_manager.db_connection.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error removing submission from database: {e}")
            return False

    def _generate_resize_report(self, start_time: datetime, resize_added: int, updated_processed: int, 
                               total_failed: int, target_count: int, final_count: int) -> Dict[str, Any]:
        """Generate resize operation report"""
        duration = datetime.now() - start_time
        
        return {
            'total_tickets': final_count,
            'resize_added': resize_added,
            'updated_processed': updated_processed,
            'total_processed': resize_added + updated_processed,
            'total_failed': total_failed,
            'duration': str(duration),
            'resize_mode': True,
            'target_count': target_count,
            'final_count': final_count,
            'report_path': 'feedback_knowledge_summary.txt'  # Generated separately
        }
    
    def test_child_count_change(self, ticket_key: str, new_child_count: int = 3) -> bool:
        """Test function to simulate a ticket with changed descendant count"""
        # This would be implemented to modify the database for testing
        # For now, just log the operation
        self.logger.info(f"TEST MODE: Would simulate descendant count change for {ticket_key} to {new_child_count}")
        return True
    
