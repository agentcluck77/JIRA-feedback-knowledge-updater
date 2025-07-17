#!/usr/bin/env python3
"""
Configuration management for Feedback Knowledge Updater
"""

import os
import json
import logging
from typing import Dict, Any


def setup_logging(log_level=logging.INFO):
    """Setup logging configuration"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('feedback_updater.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    try:
        # Load from .env file if it exists
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
        
        # Build configuration from environment variables
        config = {
            'jira': {
                'server': os.getenv('JIRA_SERVER'),
                'username': os.getenv('JIRA_USERNAME'),
                'password': os.getenv('JIRA_PASSWORD'),
                'verify': os.getenv('JIRA_VERIFY', 'true').lower() == 'true',
                'project_key': os.getenv('JIRA_PROJECT_KEY'),
                'parent_query': os.getenv('JIRA_PARENT_QUERY')
            }
        }
        
        # Load summarizer bot configurations
        from .bot_config import merge_summarizer_bot_configs, get_summarizer_bot_config
        summarizer_config = get_summarizer_bot_config('default')
        if summarizer_config:
            config['summarizer_bot_api'] = summarizer_config
        else:
            # Fallback to environment variables if no JSON config
            config['summarizer_bot_api'] = {
                'url': os.getenv('SUMMARIZER_BOT_URL'),
                'app_id': os.getenv('SUMMARIZER_BOT_APP_ID'),
                'user_email': os.getenv('SUMMARIZER_BOT_USER_EMAIL')
            }
        
        # Handle classifier bot configuration - support both new JSON format and legacy single bot
        classifier_bots_config = os.getenv('CLASSIFIER_BOTS_CONFIG')
        if classifier_bots_config:
            try:
                config['classifier_bots'] = json.loads(classifier_bots_config)
                # Add default bot_type for configs without it (backward compatibility)
                for bot_name, bot_config in config['classifier_bots'].items():
                    if 'bot_type' not in bot_config:
                        bot_config['bot_type'] = 'ai_bot_platform'
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON in CLASSIFIER_BOTS_CONFIG: {e}")
        else:
            # Fallback to legacy single bot configuration
            legacy_config = {
                'bot_type': 'ai_bot_platform',  # Default for legacy configs
                'url': os.getenv('CLASSIFIER_BOT_URL'),
                'app_id': os.getenv('CLASSIFIER_BOT_APP_ID'),
                'user_email': os.getenv('CLASSIFIER_BOT_USER_EMAIL')
            }
            # Only create default bot if all legacy values are present
            if all([legacy_config['url'], legacy_config['app_id'], legacy_config['user_email']]):
                config['classifier_bots'] = {'default': legacy_config}
            else:
                config['classifier_bots'] = {}
        
        # Merge with local file configurations (local file takes precedence)
        from .bot_config import load_classifier_bots_from_file
        local_bots = load_classifier_bots_from_file()
        config['classifier_bots'].update(local_bots)
        
        # Validate required configuration
        required_vars = [
            ('JIRA_SERVER', config['jira']['server']),
            ('JIRA_USERNAME', config['jira']['username']),
            ('JIRA_PASSWORD', config['jira']['password']),
            ('JIRA_PARENT_QUERY', config['jira']['parent_query'])
        ]
        
        # Only validate summarizer bot config if it's configured
        summarizer_config = config.get('summarizer_bot_api', {})
        if summarizer_config.get('url'):  # Only validate if there's actually a config
            bot_type = summarizer_config.get('bot_type', 'ai_bot_platform')
            
            # Always require URL
            required_vars.append(('SUMMARIZER_BOT_URL', summarizer_config.get('url')))
            
            # For AI Bot Platform, require app_id and user_email
            if bot_type == 'ai_bot_platform':
                required_vars.extend([
                    ('SUMMARIZER_BOT_APP_ID', summarizer_config.get('app_id')),
                    ('SUMMARIZER_BOT_USER_EMAIL', summarizer_config.get('user_email'))
                ])
            # For Alpha Knowledge, require expert_id and api_key
            elif bot_type == 'alpha_knowledge':
                required_vars.extend([
                    ('SUMMARIZER_BOT_EXPERT_ID', summarizer_config.get('expert_id')),
                    ('SUMMARIZER_BOT_API_KEY', summarizer_config.get('api_key'))
                ])
        
        for var_name, var_value in required_vars:
            if not var_value:
                raise Exception(f"Missing required environment variable: {var_name}")
        
        return config
    except Exception as e:
        raise Exception(f"Error loading configuration from environment variables: {e}") 