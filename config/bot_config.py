#!/usr/bin/env python3
"""
Bot configuration management for classifier bots.
Handles loading from files, validation, and interactive management.
"""

import os
import json
from typing import Dict, List, Any, Optional


def load_classifier_bots_from_file() -> Dict[str, Any]:
    """Load classifier bot configurations from local config file"""
    config_file = 'classifier_bots_config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error reading config file: {e}")
            return {}
    return {}


def save_classifier_bots_to_file(bots_config: Dict[str, Any]) -> bool:
    """Save classifier bot configurations to local config file"""
    config_file = 'classifier_bots_config.json'
    try:
        with open(config_file, 'w') as f:
            json.dump(bots_config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config file: {e}")
        return False


def load_summarizer_bots_from_file() -> Dict[str, Any]:
    """Load summarizer bot configurations from local config file"""
    config_file = 'summarizer_bots_config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error reading summarizer config file: {e}")
            return {}
    return {}


def save_summarizer_bots_to_file(bots_config: Dict[str, Any]) -> bool:
    """Save summarizer bot configurations to local config file"""
    config_file = 'summarizer_bots_config.json'
    try:
        with open(config_file, 'w') as f:
            json.dump(bots_config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving summarizer config file: {e}")
        return False


def merge_classifier_bot_configs() -> Dict[str, Any]:
    """Merge classifier bot configs from environment and local file"""
    # Start with environment config
    env_config = os.getenv('CLASSIFIER_BOTS_CONFIG')
    if env_config:
        try:
            bots_config = json.loads(env_config)
        except json.JSONDecodeError:
            bots_config = {}
    else:
        bots_config = {}
    
    # Merge with local file (local file takes precedence)
    local_bots = load_classifier_bots_from_file()
    bots_config.update(local_bots)
    
    return bots_config


def merge_summarizer_bot_configs() -> Dict[str, Any]:
    """Merge summarizer bot configs from environment and local file"""
    # Start with environment config (legacy support)
    env_config = {
        'url': os.getenv('SUMMARIZER_BOT_URL'),
        'app_id': os.getenv('SUMMARIZER_BOT_APP_ID'),
        'user_email': os.getenv('SUMMARIZER_BOT_USER_EMAIL'),
        'app_secret': os.getenv('SUMMARIZER_BOT_APP_SECRET')
    }
    
    # Only create legacy config if all required values are present
    bots_config = {}
    if all([env_config['url'], env_config['app_id'], env_config['user_email']]):
        bots_config['legacy'] = env_config
    
    # Merge with local file (local file takes precedence)
    local_bots = load_summarizer_bots_from_file()
    bots_config.update(local_bots)
    
    return bots_config


def get_summarizer_bot_config(bot_name: str = 'default') -> Optional[Dict[str, Any]]:
    """Get configuration for a specific summarizer bot"""
    merged_config = merge_summarizer_bot_configs()
    return merged_config.get(bot_name)


def list_available_summarizer_bots() -> List[Dict[str, str]]:
    """List all available summarizer bots with type information"""
    merged_config = merge_summarizer_bot_configs()
    
    if not merged_config:
        return []
    
    bot_list = []
    for bot_name, bot_config in merged_config.items():
        bot_type = bot_config.get('bot_type', 'ai_bot_platform')
        bot_list.append({
            'name': bot_name,
            'type': bot_type,
            'display': f"{bot_name} ({get_bot_type_display_name(bot_type)})"
        })
    
    return bot_list


def validate_summarizer_bot_selection(selected_bot: str) -> bool:
    """Validate that the selected summarizer bot exists in configuration"""
    merged_config = merge_summarizer_bot_configs()
    available_bots = list(merged_config.keys())
    
    if not available_bots:
        raise Exception("No summarizer bots configured. Please configure bots in summarizer_bots_config.json")
    
    if selected_bot not in available_bots:
        raise Exception(f"Summarizer bot '{selected_bot}' not found. Available bots: {', '.join(available_bots)}")
    
    # Validate the bot configuration
    bot_config = merged_config[selected_bot]
    try:
        validate_bot_config(selected_bot, bot_config)
    except Exception as e:
        raise Exception(f"Summarizer bot '{selected_bot}' has invalid configuration: {str(e)}")
    
    return True


def validate_bot_config(bot_name: str, bot_config: Dict[str, Any]) -> None:
    """Validate bot configuration based on bot type"""
    bot_type = bot_config.get('bot_type', 'ai_bot_platform')
    
    if bot_type == 'ai_bot_platform':
        required_fields = ['url', 'app_id', 'user_email']
        for field in required_fields:
            if not bot_config.get(field):
                raise Exception(f"Missing required field '{field}' for AI Bot Platform bot '{bot_name}'")
    
    elif bot_type == 'alpha_knowledge':
        required_fields = ['url', 'expert_id', 'api_key']
        for field in required_fields:
            if not bot_config.get(field):
                raise Exception(f"Missing required field '{field}' for Alpha Knowledge bot '{bot_name}'")
    
    else:
        raise Exception(f"Unsupported bot type '{bot_type}' for bot '{bot_name}'")


def get_bot_type_display_name(bot_type: str) -> str:
    """Get display name for bot type"""
    display_names = {
        'ai_bot_platform': 'AI Bot Platform',
        'alpha_knowledge': 'Alpha Knowledge'
    }
    return display_names.get(bot_type, bot_type)


def list_available_classifier_bots(config: Optional[Dict] = None) -> List[Dict[str, str]]:
    """List all available classifier bots with type information"""
    # Get merged configuration (includes both env vars and file config)
    merged_config = merge_classifier_bot_configs()
    
    if not merged_config:
        return []
    
    bot_list = []
    for bot_name, bot_config in merged_config.items():
        bot_type = bot_config.get('bot_type', 'ai_bot_platform')
        bot_list.append({
            'name': bot_name,
            'type': bot_type,
            'display': f"{bot_name} ({get_bot_type_display_name(bot_type)})"
        })
    
    return bot_list


def validate_classifier_bot_selection(config: Dict, selected_bot: str) -> bool:
    """Validate that the selected classifier bot exists in configuration"""
    # Use merged configuration to check all available bots
    merged_config = merge_classifier_bot_configs()
    available_bots = list(merged_config.keys())
    
    if not available_bots:
        raise Exception("No classifier bots configured. Please set CLASSIFIER_BOTS_CONFIG environment variable or use the interactive configuration manager.")
    
    if selected_bot not in available_bots:
        raise Exception(f"Classifier bot '{selected_bot}' not found. Available bots: {', '.join(available_bots)}")
    
    # Validate the bot configuration
    bot_config = merged_config[selected_bot]
    try:
        validate_bot_config(selected_bot, bot_config)
    except Exception as e:
        raise Exception(f"Classifier bot '{selected_bot}' has invalid configuration: {str(e)}")
    
    return True


def view_classifier_bot_configs() -> None:
    """View all configured classifier bots"""
    print("\n=== Classifier Bot Configurations ===")
    
    # Show environment-based configs
    env_config = os.getenv('CLASSIFIER_BOTS_CONFIG')
    if env_config:
        try:
            env_bots = json.loads(env_config)
            if env_bots:
                print("\nEnvironment-based configurations:")
                for bot_name, bot_config in env_bots.items():
                    bot_type = bot_config.get('bot_type', 'ai_bot_platform')
                    print(f"  {bot_name} ({get_bot_type_display_name(bot_type)})")
                    if bot_type == 'ai_bot_platform':
                        print(f"    URL: {bot_config.get('url', 'Not set')}")
                        print(f"    App ID: {bot_config.get('app_id', 'Not set')}")
                        print(f"    User Email: {bot_config.get('user_email', 'Not set')}")
                    elif bot_type == 'alpha_knowledge':
                        print(f"    URL: {bot_config.get('url', 'Not set')}")
                        print(f"    Expert ID: {bot_config.get('expert_id', 'Not set')}")
                        print(f"    API Key: {'***' if bot_config.get('api_key') else 'Not set'}")
        except json.JSONDecodeError:
            print("Invalid JSON in CLASSIFIER_BOTS_CONFIG environment variable")
    
    # Show file-based configs
    local_bots = load_classifier_bots_from_file()
    if local_bots:
        print("\nFile-based configurations (classifier_bots_config.json):")
        for bot_name, bot_config in local_bots.items():
            bot_type = bot_config.get('bot_type', 'ai_bot_platform')
            print(f"  {bot_name} ({get_bot_type_display_name(bot_type)})")
            if bot_type == 'ai_bot_platform':
                print(f"    URL: {bot_config.get('url', 'Not set')}")
                print(f"    App ID: {bot_config.get('app_id', 'Not set')}")
                print(f"    User Email: {bot_config.get('user_email', 'Not set')}")
            elif bot_type == 'alpha_knowledge':
                print(f"    URL: {bot_config.get('url', 'Not set')}")
                print(f"    Expert ID: {bot_config.get('expert_id', 'Not set')}")
                print(f"    API Key: {'***' if bot_config.get('api_key') else 'Not set'}")
    
    if not env_config and not local_bots:
        print("No classifier bots configured.")
        print("Use option 2 to add a new bot configuration.")


def add_classifier_bot() -> None:
    """Add a new classifier bot configuration"""
    print("\n=== Add New Classifier Bot ===")
    
    # Get bot name
    bot_name = input("Enter bot name: ").strip()
    if not bot_name:
        print("❌ Bot name cannot be empty")
        return
    
    # Check if bot already exists
    existing_bots = load_classifier_bots_from_file()
    if bot_name in existing_bots:
        overwrite = input(f"Bot '{bot_name}' already exists. Overwrite? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("Operation cancelled")
            return
    
    # Get bot type
    print("\nSelect bot type:")
    print("1. AI Bot Platform")
    print("2. Alpha Knowledge")
    
    while True:
        choice = input("Enter choice (1-2): ").strip()
        if choice == '1':
            bot_type = 'ai_bot_platform'
            break
        elif choice == '2':
            bot_type = 'alpha_knowledge'
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")
    
    # Collect configuration based on bot type
    bot_config = {'bot_type': bot_type}
    
    if bot_type == 'ai_bot_platform':
        print(f"\nConfiguring AI Bot Platform bot '{bot_name}':")
        bot_config['url'] = input("Enter Bot URL: ").strip()
        bot_config['app_id'] = input("Enter App ID: ").strip()
        bot_config['user_email'] = input("Enter User Email: ").strip()
        
        # Optionally collect app_secret
        collect_secret = input("Do you want to store the app secret in config file? (y/N): ").strip().lower()
        if collect_secret == 'y':
            bot_config['app_secret'] = input("Enter App Secret: ").strip()
            print("⚠️  Note: App secret stored in config file. Consider using environment variables for production.")
        else:
            print(f"💡 Remember to set environment variable: CLASSIFIER_BOT_{bot_name.upper()}_APP_SECRET")
    
    elif bot_type == 'alpha_knowledge':
        print(f"\nConfiguring Alpha Knowledge bot '{bot_name}':")
        bot_config['url'] = input("Enter API URL: ").strip()
        bot_config['expert_id'] = input("Enter Expert ID: ").strip()
        bot_config['api_key'] = input("Enter API Key: ").strip()
    
    # Validate configuration
    try:
        validate_bot_config(bot_name, bot_config)
    except Exception as e:
        print(f"❌ Invalid configuration: {e}")
        return
    
    # Save to file
    existing_bots[bot_name] = bot_config
    if save_classifier_bots_to_file(existing_bots):
        print(f"✅ Bot '{bot_name}' added successfully!")
    else:
        print(f"❌ Failed to save bot configuration")


def edit_classifier_bot() -> None:
    """Edit an existing classifier bot configuration"""
    print("\n=== Edit Classifier Bot ===")
    
    existing_bots = load_classifier_bots_from_file()
    if not existing_bots:
        print("No bots configured in local file. Use option 2 to add a bot first.")
        return
    
    # Show available bots
    print("\nAvailable bots:")
    bot_names = list(existing_bots.keys())
    for i, bot_name in enumerate(bot_names, 1):
        bot_type = existing_bots[bot_name].get('bot_type', 'ai_bot_platform')
        print(f"{i}. {bot_name} ({get_bot_type_display_name(bot_type)})")
    
    # Get selection
    while True:
        try:
            choice = int(input(f"\nSelect bot to edit (1-{len(bot_names)}): "))
            if 1 <= choice <= len(bot_names):
                selected_bot = bot_names[choice - 1]
                break
            else:
                print("Invalid selection")
        except ValueError:
            print("Please enter a number")
    
    # Edit the selected bot
    bot_config = existing_bots[selected_bot].copy()
    bot_type = bot_config.get('bot_type', 'ai_bot_platform')
    
    print(f"\nEditing bot '{selected_bot}' ({get_bot_type_display_name(bot_type)}):")
    print("Press Enter to keep current value, or enter new value:")
    
    if bot_type == 'ai_bot_platform':
        new_url = input(f"Bot URL [{bot_config.get('url', '')}]: ").strip()
        if new_url:
            bot_config['url'] = new_url
        
        new_app_id = input(f"App ID [{bot_config.get('app_id', '')}]: ").strip()
        if new_app_id:
            bot_config['app_id'] = new_app_id
        
        new_email = input(f"User Email [{bot_config.get('user_email', '')}]: ").strip()
        if new_email:
            bot_config['user_email'] = new_email
        
        # Handle app_secret
        if 'app_secret' in bot_config:
            update_secret = input("Update stored app secret? (y/N): ").strip().lower()
            if update_secret == 'y':
                new_secret = input("Enter new App Secret: ").strip()
                if new_secret:
                    bot_config['app_secret'] = new_secret
        else:
            add_secret = input("Add app secret to config file? (y/N): ").strip().lower()
            if add_secret == 'y':
                new_secret = input("Enter App Secret: ").strip()
                if new_secret:
                    bot_config['app_secret'] = new_secret
    
    elif bot_type == 'alpha_knowledge':
        new_url = input(f"API URL [{bot_config.get('url', '')}]: ").strip()
        if new_url:
            bot_config['url'] = new_url
        
        new_expert_id = input(f"Expert ID [{bot_config.get('expert_id', '')}]: ").strip()
        if new_expert_id:
            bot_config['expert_id'] = new_expert_id
        
        new_api_key = input(f"API Key [{'***' if bot_config.get('api_key') else ''}]: ").strip()
        if new_api_key:
            bot_config['api_key'] = new_api_key
    
    # Validate and save
    try:
        validate_bot_config(selected_bot, bot_config)
        existing_bots[selected_bot] = bot_config
        if save_classifier_bots_to_file(existing_bots):
            print(f"✅ Bot '{selected_bot}' updated successfully!")
        else:
            print(f"❌ Failed to save bot configuration")
    except Exception as e:
        print(f"❌ Invalid configuration: {e}")


def remove_classifier_bot() -> None:
    """Remove a classifier bot configuration"""
    print("\n=== Remove Classifier Bot ===")
    
    existing_bots = load_classifier_bots_from_file()
    if not existing_bots:
        print("No bots configured in local file.")
        return
    
    # Show available bots
    print("\nAvailable bots:")
    bot_names = list(existing_bots.keys())
    for i, bot_name in enumerate(bot_names, 1):
        bot_type = existing_bots[bot_name].get('bot_type', 'ai_bot_platform')
        print(f"{i}. {bot_name} ({get_bot_type_display_name(bot_type)})")
    
    # Get selection
    while True:
        try:
            choice = int(input(f"\nSelect bot to remove (1-{len(bot_names)}): "))
            if 1 <= choice <= len(bot_names):
                selected_bot = bot_names[choice - 1]
                break
            else:
                print("Invalid selection")
        except ValueError:
            print("Please enter a number")
    
    # Confirm removal
    confirm = input(f"Are you sure you want to remove bot '{selected_bot}'? (y/N): ").strip().lower()
    if confirm == 'y':
        del existing_bots[selected_bot]
        if save_classifier_bots_to_file(existing_bots):
            print(f"✅ Bot '{selected_bot}' removed successfully!")
        else:
            print(f"❌ Failed to save configuration")
    else:
        print("Operation cancelled")


def rename_classifier_bot() -> None:
    """Rename a classifier bot"""
    print("\n=== Rename Classifier Bot ===")
    
    existing_bots = load_classifier_bots_from_file()
    if not existing_bots:
        print("No bots configured in local file.")
        return
    
    # Show available bots
    print("\nAvailable bots:")
    bot_names = list(existing_bots.keys())
    for i, bot_name in enumerate(bot_names, 1):
        bot_type = existing_bots[bot_name].get('bot_type', 'ai_bot_platform')
        print(f"{i}. {bot_name} ({get_bot_type_display_name(bot_type)})")
    
    # Get selection
    while True:
        try:
            choice = int(input(f"\nSelect bot to rename (1-{len(bot_names)}): "))
            if 1 <= choice <= len(bot_names):
                old_name = bot_names[choice - 1]
                break
            else:
                print("Invalid selection")
        except ValueError:
            print("Please enter a number")
    
    # Get new name
    new_name = input(f"Enter new name for '{old_name}': ").strip()
    if not new_name:
        print("❌ Name cannot be empty")
        return
    
    if new_name in existing_bots:
        print(f"❌ Bot '{new_name}' already exists")
        return
    
    # Rename
    existing_bots[new_name] = existing_bots[old_name]
    del existing_bots[old_name]
    
    if save_classifier_bots_to_file(existing_bots):
        print(f"✅ Bot renamed from '{old_name}' to '{new_name}' successfully!")
    else:
        print(f"❌ Failed to save configuration")


def manage_classifier_bot_configs() -> None:
    """Interactive menu for managing classifier bot configurations"""
    while True:
        print("\n=== Classifier Bot Configuration Manager ===")
        print("1. View current configurations")
        print("2. Add new bot")
        print("3. Edit existing bot")
        print("4. Remove bot")
        print("5. Rename bot")
        print("6. Return to main menu")
        
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            view_classifier_bot_configs()
        elif choice == '2':
            add_classifier_bot()
        elif choice == '3':
            edit_classifier_bot()
        elif choice == '4':
            remove_classifier_bot()
        elif choice == '5':
            rename_classifier_bot()
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please enter a number between 1-6.") 