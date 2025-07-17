#!/usr/bin/env python3
"""
Alpha Knowledge Summarizer Client
Implements the Alpha Knowledge chat completion API for summarization tasks
"""

import requests
import json
import logging
from typing import Dict, Any, Optional, Tuple


class AlphaSummarizerClient:
    """Client for Alpha Knowledge summarization operations using chat completions"""
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """Initialize Alpha Summarizer client
        
        Args:
            config (dict): Bot configuration containing url, expert_id, api_key
            logger: Logger instance
        """
        self.base_url = config['url'].rstrip('/')
        self.expert_id = config['expert_id']
        self.api_key = config['api_key']
        self.logger = logger
        
        # Prepare headers for API requests
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # Build the chat completions endpoint
        self.chat_url = f"{self.base_url}/experts/{self.expert_id}/v2/chat/completions"
    
    def send_summarization_request(self, content: str, user_email: str = "system@example.com") -> Tuple[bool, Optional[str]]:
        """Send content to Alpha Knowledge for summarization
        
        Args:
            content (str): The content to summarize (ticket information)
            user_email (str): User identifier for auditing purposes
            
        Returns:
            tuple: (success: bool, response: str or None)
        """
        try:
            # Prepare the summarization prompt
            summarization_prompt = self._build_summarization_prompt(content)
            
            # Prepare request payload according to Alpha Knowledge API spec
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": summarization_prompt
                    }
                ],
                "user": user_email,
                "stream": False
            }
            # Log raw payload for debugging
            self.logger.debug(f"Alpha Knowledge chat payload: {json.dumps(payload)}")
            
            self.logger.debug(f"Sending summarization request to Alpha Knowledge: {self.chat_url}")
            
            # Send request
            response = requests.post(
                self.chat_url,
                headers=self.headers,
                json=payload,
                timeout=60  # Longer timeout for summarization
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Extract the summary from the response
                summary = self._extract_summary_from_response(response_data)
                
                if summary:
                    self.logger.info("Successfully received summarization from Alpha Knowledge")
                    return True, summary
                else:
                    self.logger.warning("Empty or invalid response from Alpha Knowledge")
                    return False, None
            else:
                self.logger.error(f"Alpha Knowledge API error: {response.status_code} - {response.text}")
                return False, None
                
        except requests.exceptions.Timeout:
            self.logger.error("Timeout while waiting for Alpha Knowledge response")
            return False, None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error while contacting Alpha Knowledge: {e}")
            return False, None
        except Exception as e:
            self.logger.error(f"Unexpected error during Alpha Knowledge summarization: {e}")
            return False, None
    
    def _build_summarization_prompt(self, content: str) -> str:
        """Build an effective summarization prompt for Alpha Knowledge
        
        Args:
            content (str): Raw ticket content
            
        Returns:
            str: Formatted prompt for summarization
        """
        prompt = f"""Please analyze and summarize the following JIRA ticket information. Provide a concise, structured summary that captures the key issues, patterns, and actionable insights.

Focus on:
1. Main problem or request
2. Key patterns across related tickets
3. Common pain points or blockers
4. Suggested actions or solutions

Ticket Information:
{content}

Please provide a clear, actionable summary in 2-3 paragraphs."""
        
        return prompt
    
    def _extract_summary_from_response(self, response_data: Dict[str, Any]) -> Optional[str]:
        """Extract the summary content from Alpha Knowledge response
        
        Args:
            response_data (dict): Response from Alpha Knowledge API
            
        Returns:
            str or None: Extracted summary content
        """
        try:
            # According to Alpha Knowledge API docs, the actual content is in choices[0]
            choices = response_data.get('choices', [])
            if not choices:
                self.logger.error("No choices in Alpha Knowledge response")
                return None
            
            # Get the main response content (index 0)
            main_choice = choices[0]
            message = main_choice.get('message', {})
            content = message.get('content', '').strip()
            
            if not content:
                self.logger.error("Empty content in Alpha Knowledge response")
                return None
            
            # Validate content quality - check for error messages and minimum length
            if self._is_error_response(content):
                self.logger.error(f"Alpha Knowledge returned error message instead of summary: {content[:100]}...")
                return None
            
            if len(content.strip()) < 50:
                self.logger.error(f"Alpha Knowledge returned insufficient content (length: {len(content)}): {content[:100]}...")
                return None
            
            # Extract metadata if available (choices[1] contains citations, etc.)
            metadata = None
            if len(choices) > 1:
                try:
                    metadata_content = choices[1].get('message', {}).get('content', '')
                    if metadata_content:
                        metadata = json.loads(metadata_content)
                        self.logger.debug(f"Alpha Knowledge metadata: {metadata}")
                except (json.JSONDecodeError, KeyError):
                    self.logger.debug("No valid metadata in Alpha Knowledge response")
            
            # If we have citations, append them to the summary
            if metadata and metadata.get('citations'):
                citations_text = "\n\nSources:"
                for i, citation in enumerate(metadata['citations'], 1):
                    title = citation.get('title', 'Unknown source')
                    citations_text += f"\n[{i}] {title}"
                content += citations_text
            
            return content
            
        except Exception as e:
            self.logger.error(f"Error extracting summary from Alpha Knowledge response: {e}")
            return None
    
    def _is_error_response(self, content: str) -> bool:
        """Check if the response content is an error message rather than a proper summary
        
        Args:
            content (str): The response content to validate
            
        Returns:
            bool: True if content appears to be an error message
        """
        content_lower = content.lower().strip()
        
        # Common error message patterns
        error_patterns = [
            "i'm sorry",
            "i am sorry", 
            "couldn't find",
            "could not find",
            "couldn't answer",
            "could not answer",
            "insufficient information",
            "insufficient data",
            "not enough information",
            "please try again",
            "please rephrase",
            "please provide more details",
            "unable to process",
            "unable to answer",
            "try rephrasing",
            "no information available",
            "information not available"
        ]
        
        # Check if content starts with or contains common error patterns
        for pattern in error_patterns:
            if pattern in content_lower:
                return True
        
        # Check for very generic responses that indicate failure
        generic_patterns = [
            "i don't understand",
            "i cannot help",
            "please clarify",
            "more context needed"
        ]
        
        for pattern in generic_patterns:
            if pattern in content_lower:
                return True
                
        return False
    
    def test_connection(self) -> bool:
        """Test connection to Alpha Knowledge API
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Send a simple test request
            test_payload = {
                "messages": [
                    {
                        "role": "user", 
                        "content": "Hello, this is a connection test."
                    }
                ],
                "user": "test@example.com",
                "stream": False
            }
            
            response = requests.post(
                self.chat_url,
                headers=self.headers,
                json=test_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                self.logger.info("Alpha Knowledge summarizer connection test successful")
                return True
            else:
                self.logger.error(f"Alpha Knowledge connection test failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Alpha Knowledge connection test error: {e}")
            return False 