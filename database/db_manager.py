#!/usr/bin/env python3
"""
Database management for Feedback Knowledge Updater
"""

import sqlite3
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any


class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path: str = 'feedback_updater.db', logger: Optional[logging.Logger] = None):
        self.db_path = db_path
        self.logger = logger or logging.getLogger(__name__)
        self.db_connection = None
        self.initialize_database()
    
    def initialize_database(self) -> None:
        """Initialize SQLite database with all required tables"""
        try:
            self.db_connection = sqlite3.connect(self.db_path)
            db_query = self.db_connection.cursor()
            
            # Create main tables
            db_query.execute('''
                CREATE TABLE IF NOT EXISTS ticket_index (
                    ticket_key VARCHAR(20) PRIMARY KEY,
                    summary TEXT,
                    child_count INTEGER DEFAULT 0,
                    last_updated TIMESTAMP,
                    created_date TIMESTAMP,
                    summary_hash VARCHAR(64),
                    bot_request_id TEXT,
                    bot_response TEXT,
                    bot_response_received BOOLEAN DEFAULT FALSE,
                    processed_version INTEGER DEFAULT 1
                )
            ''')
            
            db_query.execute('''
                CREATE TABLE IF NOT EXISTS child_tickets (
                    parent_key VARCHAR(20),
                    child_key VARCHAR(20),
                    summary TEXT,
                    last_updated TIMESTAMP,
                    PRIMARY KEY (parent_key, child_key)
                )
            ''')
            
            db_query.execute('''
                CREATE TABLE IF NOT EXISTS bot_requests (
                    request_id TEXT PRIMARY KEY,
                    ticket_key TEXT,
                    request_content TEXT,
                    request_timestamp TIMESTAMP,
                    response_content TEXT,
                    response_timestamp TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            db_query.execute('''
                CREATE TABLE IF NOT EXISTS classifier_bot_submissions (
                    ticket_key VARCHAR(20),
                    bot_name VARCHAR(50),
                    summary_text TEXT,
                    summary_hash VARCHAR(64),
                    action_type VARCHAR(10) DEFAULT 'add',
                    submission_timestamp TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    doc_id TEXT,
                    bot_type TEXT DEFAULT 'ai_bot_platform',
                    alpha_knowledge_id INTEGER,
                    PRIMARY KEY (ticket_key, bot_name)
                )
            ''')
            
            # Run migrations
            self._run_migrations(db_query)
            
            self.db_connection.commit()
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise
    
    def _run_migrations(self, db_query: sqlite3.Cursor) -> None:
        """Run database migrations to add new columns"""
        migrations = [
            # Add bot_name column for multi-bot support
            {
                'column': 'bot_name',
                'table': 'classifier_bot_submissions',
                'sql': 'ALTER TABLE classifier_bot_submissions ADD COLUMN bot_name VARCHAR(50)',
                'update_sql': "UPDATE classifier_bot_submissions SET bot_name = 'default' WHERE bot_name IS NULL"
            },
            # Add doc_id column for document tracking
            {
                'column': 'doc_id',
                'table': 'classifier_bot_submissions',
                'sql': 'ALTER TABLE classifier_bot_submissions ADD COLUMN doc_id TEXT',
                'update_sql': None
            },
            # Add bot_type column for classifier bot support
            {
                'column': 'bot_type',
                'table': 'classifier_bot_submissions',
                'sql': 'ALTER TABLE classifier_bot_submissions ADD COLUMN bot_type TEXT DEFAULT "ai_bot_platform"',
                'update_sql': "UPDATE classifier_bot_submissions SET bot_type = 'ai_bot_platform' WHERE bot_type IS NULL"
            },
            # Add alpha_knowledge_id for Alpha Knowledge tracking
            {
                'column': 'alpha_knowledge_id',
                'table': 'classifier_bot_submissions',
                'sql': 'ALTER TABLE classifier_bot_submissions ADD COLUMN alpha_knowledge_id INTEGER',
                'update_sql': None
            },
            # Add processed_version for ticket versioning
            {
                'column': 'processed_version',
                'table': 'ticket_index',
                'sql': 'ALTER TABLE ticket_index ADD COLUMN processed_version INTEGER DEFAULT 1',
                'update_sql': "UPDATE ticket_index SET processed_version = 1 WHERE processed_version IS NULL"
            }
        ]
        
        for migration in migrations:
            try:
                db_query.execute(migration['sql'])
                self.logger.info(f"Added {migration['column']} column to {migration['table']} table")
                
                if migration['update_sql']:
                    db_query.execute(migration['update_sql'])
                    self.db_connection.commit()
                    self.logger.info(f"Updated existing records in {migration['table']} table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    self.logger.debug(f"{migration['column']} column already exists")
                else:
                    raise
    
    def get_existing_tickets(self) -> Dict[str, Dict]:
        """Get all existing tickets from database"""
        if not self.db_connection:
            return {}
        
        try:
            db_query = self.db_connection.cursor()
            db_query.execute('''
                SELECT ticket_key, summary, child_count, last_updated, 
                       created_date, summary_hash, bot_request_id, bot_response,
                       bot_response_received, processed_version
                FROM ticket_index
            ''')
            
            tickets = {}
            for row in db_query.fetchall():
                tickets[row[0]] = {
                    'summary': row[1],
                    'child_count': row[2],
                    'last_updated': row[3],
                    'created_date': row[4],
                    'summary_hash': row[5],
                    'bot_request_id': row[6],
                    'bot_response': row[7],
                    'bot_response_received': bool(row[8]),
                    'processed_version': row[9] or 1
                }
            
            return tickets
        except Exception as e:
            self.logger.error(f"Error retrieving existing tickets: {e}")
            return {}
    
    def save_ticket_to_database(self, ticket_key: str, summary: str, child_tickets=None, bot_request_id=None) -> None:
        """Save ticket information to database"""
        if not self.db_connection:
            self.logger.error("Database connection not initialized")
            return
        
        try:
            db_query = self.db_connection.cursor()
            
            # Generate summary hash
            summary_hash = hashlib.sha256(summary.encode('utf-8')).hexdigest()
            
            # Insert or update main ticket
            current_time = datetime.now()
            child_count = len(child_tickets) if child_tickets else 0
            
            db_query.execute('''
                INSERT OR REPLACE INTO ticket_index 
                (ticket_key, summary, child_count, last_updated, created_date, 
                 summary_hash, bot_request_id, bot_response, bot_response_received, processed_version)
                VALUES (?, ?, ?, ?, COALESCE((SELECT created_date FROM ticket_index WHERE ticket_key = ?), ?), 
                        ?, ?, ?, ?, ?)
            ''', (ticket_key, summary, child_count, current_time, ticket_key, current_time,
                  summary_hash, bot_request_id, summary, True, 1))
            
            # Save child tickets if provided
            if child_tickets:
                # Clear existing child tickets
                db_query.execute('DELETE FROM child_tickets WHERE parent_key = ?', (ticket_key,))
                
                # Insert new child tickets (replace existing entries on duplicate keys), ignore constraint errors
                for child_ticket in child_tickets:
                    try:
                        db_query.execute('''
                            INSERT OR REPLACE INTO child_tickets (parent_key, child_key, summary, last_updated)
                            VALUES (?, ?, ?, ?)
                        ''', (ticket_key, child_ticket.key, child_ticket.fields.summary, current_time))
                    except sqlite3.IntegrityError as ie:
                        # This should be rare due to OR REPLACE, but ignore any uniqueness errors
                        self.logger.debug(f"Ignored duplicate child ticket {ticket_key}-{child_ticket.key}: {ie}")
            
            self.db_connection.commit()
            self.logger.debug(f"Saved ticket {ticket_key} to database")
            
        except Exception as e:
            self.logger.error(f"Error saving ticket {ticket_key}: {e}")
            self.db_connection.rollback()
    
    def get_classifier_submissions(self) -> Dict[str, Dict]:
        """Get all classifier bot submissions"""
        if not self.db_connection:
            return {}
        
        try:
            db_query = self.db_connection.cursor()
            db_query.execute('''
                SELECT ticket_key, bot_name, summary_text, summary_hash, 
                       action_type, submission_timestamp, status, doc_id,
                       bot_type, alpha_knowledge_id
                FROM classifier_bot_submissions
            ''')
            
            submissions = {}
            for row in db_query.fetchall():
                key = f"{row[0]}:{row[1]}"  # ticket_key:bot_name
                submissions[key] = {
                    'ticket_key': row[0],
                    'bot_name': row[1],
                    'summary_text': row[2],
                    'summary_hash': row[3],
                    'action_type': row[4],
                    'submission_timestamp': row[5],
                    'status': row[6],
                    'doc_id': row[7],
                    'bot_type': row[8],
                    'alpha_knowledge_id': row[9]
                }
            
            return submissions
        except Exception as e:
            self.logger.error(f"Error retrieving classifier submissions: {e}")
            return {}
    
    def record_classifier_submission(self, ticket_key: str, bot_name: str, summary_text: str, 
                                   action_type: str = 'add', doc_id: str = None, 
                                   alpha_knowledge_id: int = None, bot_type: str = 'ai_bot_platform') -> None:
        """Record classifier bot submission"""
        if not self.db_connection:
            return
        
        try:
            db_query = self.db_connection.cursor()
            
            summary_hash = hashlib.sha256(summary_text.encode('utf-8')).hexdigest()
            current_time = datetime.now()
            
            db_query.execute('''
                INSERT OR REPLACE INTO classifier_bot_submissions 
                (ticket_key, bot_name, summary_text, summary_hash, action_type, 
                 submission_timestamp, status, doc_id, bot_type, alpha_knowledge_id)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            ''', (ticket_key, bot_name, summary_text, summary_hash, action_type,
                  current_time, doc_id, bot_type, alpha_knowledge_id))
            
            self.db_connection.commit()
            self.logger.debug(f"Recorded classifier submission for {ticket_key} with bot {bot_name}")
            
        except Exception as e:
            self.logger.error(f"Error recording classifier submission: {e}")
            self.db_connection.rollback()
    
    def clear_child_ticket_cache(self) -> None:
        """Clear child ticket cache"""
        if not self.db_connection:
            return
        
        try:
            db_query = self.db_connection.cursor()
            db_query.execute('DELETE FROM child_tickets')
            self.db_connection.commit()
            self.logger.info("Child ticket cache cleared")
        except Exception as e:
            self.logger.error(f"Error clearing child ticket cache: {e}")
    
    def get_child_tickets_for_parent(self, parent_key: str) -> List[Dict]:
        """Get child tickets for a parent ticket"""
        if not self.db_connection:
            return []
        
        try:
            db_query = self.db_connection.cursor()
            db_query.execute('''
                SELECT child_key, summary, last_updated
                FROM child_tickets
                WHERE parent_key = ?
                ORDER BY child_key
            ''', (parent_key,))
            
            child_tickets = []
            for row in db_query.fetchall():
                child_tickets.append({
                    'key': row[0],
                    'summary': row[1],
                    'last_updated': row[2]
                })
            
            return child_tickets
        except Exception as e:
            self.logger.error(f"Error retrieving child tickets for {parent_key}: {e}")
            return []
    
    def update_bot_response(self, ticket_key: str, bot_response: str) -> None:
        """Update bot response for a ticket"""
        if not self.db_connection:
            return
        
        try:
            db_query = self.db_connection.cursor()
            db_query.execute('''
                UPDATE ticket_index 
                SET bot_response = ?, bot_response_received = TRUE
                WHERE ticket_key = ?
            ''', (bot_response, ticket_key))
            
            self.db_connection.commit()
            self.logger.debug(f"Updated bot response for ticket {ticket_key}")
        except Exception as e:
            self.logger.error(f"Error updating bot response for {ticket_key}: {e}")
    
    def close(self) -> None:
        """Close database connection"""
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = None 