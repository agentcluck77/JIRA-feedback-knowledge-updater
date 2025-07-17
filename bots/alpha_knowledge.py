#!/usr/bin/env python3
"""
Alpha Knowledge API client for Feedback Knowledge Updater
"""

import os
import time
import tempfile
import requests
from datetime import datetime


class AlphaKnowledgeClient:
    """Client for Alpha Knowledge API operations"""
    
    def __init__(self, config, logger):
        """Initialize Alpha Knowledge client
        
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
    
    def upload_knowledge(self, content, citation_url, citation_title, ticket_key, max_retries=3):
        """Upload content as knowledge entry to Alpha Knowledge"""
        try:
            # Convert content to markdown format
            markdown_content = self._convert_to_markdown(content, citation_url, citation_title)
            
            # Create temporary markdown file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(markdown_content)
                temp_file_path = temp_file.name
            
            try:
                # Prepare file upload
                url = f"{self.base_url}/experts/{self.expert_id}/knowledges"
                
                # Prepare multipart form data
                files = {
                    'file': (f"{ticket_key}.md", open(temp_file_path, 'rb'), 'text/markdown')
                }
                
                # Additional form data (metadata)
                data = {
                    'citation_url': citation_url,
                    'citation_title': citation_title
                }
                
                # Remove Content-Type header for multipart uploads
                upload_headers = {k: v for k, v in self.headers.items() if k != 'Content-Type'}
                
                self.logger.info(f"Uploading knowledge to Alpha Knowledge: {citation_title}")
                
                for attempt in range(max_retries):
                    try:
                        response = requests.post(
                            url,
                            headers=upload_headers,
                            files=files,
                            data=data,
                            timeout=30
                        )
                        
                        if response.status_code in [200, 201]:
                            response_data = response.json()
                            knowledge_id = response_data.get('id')
                            if knowledge_id:
                                self.logger.info(f"Successfully uploaded knowledge entry ID: {knowledge_id}")
                                return knowledge_id
                            else:
                                self.logger.error(f"Upload successful but no ID returned: {response_data}")
                                return None
                        else:
                            self.logger.error(f"Upload failed (attempt {attempt + 1}/{max_retries}): {response.status_code} - {response.text}")
                            if attempt < max_retries - 1:
                                time.sleep(2 ** attempt)  # Exponential backoff
                                continue
                            else:
                                return None
                                
                    except requests.exceptions.RequestException as e:
                        self.logger.error(f"Network error during upload (attempt {attempt + 1}/{max_retries}): {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            return None
                
                # Close file before cleanup
                files['file'][1].close()
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass
            
        except Exception as e:
            self.logger.error(f"Error uploading knowledge to Alpha Knowledge: {str(e)}")
            return None
    
    def update_knowledge_meta(self, knowledge_id, citation_url, citation_title, max_retries=3):
        """Update metadata for existing knowledge entry
        
        Args:
            knowledge_id (int): ID of the knowledge entry to update
            citation_url (str): Updated source URL
            citation_title (str): Updated source title
            max_retries (int): Maximum number of retry attempts
            
        Returns:
            bool: True if successful, False if failed
        """
        try:
            url = f"{self.base_url}/experts/{self.expert_id}/knowledges/{knowledge_id}/meta"
            
            payload = {
                'citation_url': citation_url,
                'citation_title': citation_title
            }
            
            self.logger.info(f"Updating Alpha Knowledge knowledge entry {knowledge_id} metadata")
            
            for attempt in range(max_retries):
                try:
                    response = requests.put(
                        url,
                        headers=self.headers,
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        self.logger.info(f"Successfully updated knowledge entry {knowledge_id} metadata")
                        return True
                    else:
                        self.logger.error(f"Update failed (attempt {attempt + 1}/{max_retries}): {response.status_code} - {response.text}")
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            return False
                            
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Network error during update (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        return False
                
        except Exception as e:
            self.logger.error(f"Error updating Alpha Knowledge knowledge metadata: {str(e)}")
            return False
    
    def delete_knowledge(self, knowledge_id, max_retries=3):
        """Delete knowledge entry from Alpha Knowledge"""
        try:
            url = f"{self.base_url}/experts/{self.expert_id}/knowledges/{knowledge_id}"
            
            self.logger.info(f"Deleting Alpha Knowledge knowledge entry {knowledge_id}")
            
            for attempt in range(max_retries):
                try:
                    response = requests.delete(
                        url,
                        headers=self.headers,
                        timeout=30
                    )
                    
                    if response.status_code in [200, 204]:
                        self.logger.info(f"Successfully deleted knowledge entry {knowledge_id}")
                        return True
                    elif response.status_code == 404:
                        self.logger.warning(f"Knowledge entry {knowledge_id} not found (may already be deleted)")
                        return True  # Treat as success since the goal is achieved
                    else:
                        self.logger.error(f"Delete failed (attempt {attempt + 1}/{max_retries}): {response.status_code} - {response.text}")
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            return False
                            
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Network error during delete (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        return False
                
        except Exception as e:
            self.logger.error(f"Error deleting Alpha Knowledge knowledge: {str(e)}")
            return False
    
    def list_knowledge(self, max_retries=3):
        """List all knowledge entries for the expert"""
        try:
            url = f"{self.base_url}/experts/{self.expert_id}/knowledges"
            
            self.logger.debug("Listing Alpha Knowledge knowledge entries")
            
            for attempt in range(max_retries):
                try:
                    response = requests.get(
                        url,
                        headers=self.headers,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        knowledge_list = response.json()
                        self.logger.debug(f"Retrieved {len(knowledge_list) if isinstance(knowledge_list, list) else 'unknown'} knowledge entries")
                        return knowledge_list
                    else:
                        self.logger.error(f"List failed (attempt {attempt + 1}/{max_retries}): {response.status_code} - {response.text}")
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            return []
                            
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Network error during list (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        return []
                
        except Exception as e:
            self.logger.error(f"Error listing Alpha Knowledge knowledge: {str(e)}")
            return []
    
    def _convert_to_markdown(self, content, citation_url, citation_title):
        """Convert content to markdown format with proper citations"""
        # Clean and format the content
        cleaned_content = content.strip()
        
        # Create markdown with proper structure
        markdown = f"""# {citation_title}

## Content

{cleaned_content}

## Source

- **Citation**: [{citation_title}]({citation_url})
- **Added**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
*This knowledge entry was automatically generated from a JIRA ticket summary.*
"""
        
        return markdown 