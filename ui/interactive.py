#!/usr/bin/env python3
"""
Interactive UI for feedback knowledge updater.
Provides menu-driven interfaces for configuration and operations.
"""

import logging
from typing import Optional, Dict, Any

from config.settings import load_config
from config.bot_config import (
    manage_classifier_bot_configs,
    list_available_classifier_bots,
    validate_classifier_bot_selection,
    list_available_summarizer_bots,
    validate_summarizer_bot_selection
)
from core.updater import FeedbackKnowledgeUpdater




def run_interactive(logger: logging.Logger) -> int:
    """Run interactive mode"""
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1
    
    while True:
        try:
            print("\n" + "="*60)
            print("FEEDBACK KNOWLEDGE UPDATER - INTERACTIVE MODE")
            print("="*60)
            print("1. Run updater with specific bot")
            print("2. Manage classifier bot configurations")
            print("3. Test JIRA connection")
            print("4. Exit")
            
            choice = input("\nSelect an option (1-4): ").strip()
            
            if choice == '1':
                try:
                    result = _run_updater_with_bot(config, logger)
                    if result != 0:
                        continue
                except KeyboardInterrupt:
                    print("\n\n👋 Operation cancelled!")
                    continue
            elif choice == '2':
                try:
                    manage_classifier_bot_configs()
                except KeyboardInterrupt:
                    print("\n\n👋 Operation cancelled!")
                    continue
            elif choice == '3':
                try:
                    _test_jira_connection(config, logger)
                except KeyboardInterrupt:
                    print("\n\n👋 Operation cancelled!")
                    continue
            elif choice == '4':
                print("Goodbye!")
                return 0
            else:
                print("Invalid choice. Please enter a number between 1-4.")
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            return 0


def _run_updater_with_bot(config: Dict[str, Any], logger: logging.Logger) -> int:
    """Run updater with bot selection"""
    print("\n=== Run Updater ===")
    
    # List available bots
    available_bots = list_available_classifier_bots()
    if not available_bots:
        print("❌ No classifier bots configured.")
        print("Please configure bots using option 2 first.")
        return 1
    
    print("\nAvailable classifier bots:")
    for i, bot in enumerate(available_bots, 1):
        print(f"{i}. {bot['display']}")
    
    # Select bot
    while True:
        try:
            choice = int(input(f"\nSelect bot (1-{len(available_bots)}): "))
            if 1 <= choice <= len(available_bots):
                selected_bot = available_bots[choice - 1]['name']
                break
            else:
                print("Invalid selection")
        except ValueError:
            print("Please enter a number")
        except KeyboardInterrupt:
            print("\n\n👋 Operation cancelled!")
            return 0
    
    # Validate classifier bot selection
    try:
        validate_classifier_bot_selection(config, selected_bot)
    except Exception as e:
        print(f"❌ {e}")
        return 1

    # Select summarizer bot
    available_summarizers = list_available_summarizer_bots()
    if not available_summarizers:
        print("❌ No summarizer bots configured.")
        print("Please configure summarizer bots using option 2 first.")
        return 1
    print("\nAvailable summarizer bots:")
    for i, bot in enumerate(available_summarizers, 1):
        print(f"{i}. {bot['display']}")
    while True:
        try:
            sum_choice = int(input(f"\nSelect summarizer bot (1-{len(available_summarizers)}): "))
            if 1 <= sum_choice <= len(available_summarizers):
                selected_summarizer = available_summarizers[sum_choice - 1]['name']
                break
            else:
                print("Invalid selection")
        except ValueError:
            print("Please enter a number")
        except KeyboardInterrupt:
            print("\n\n👋 Operation cancelled!")
            return 0
    try:
        validate_summarizer_bot_selection(selected_summarizer)
    except Exception as e:
        print(f"❌ {e}")
        return 1

    # Select operation mode
    print(f"\nSelected classifier bot: {selected_bot}")
    print(f"Selected summarizer bot: {selected_summarizer}")
    print("\nSelect operation mode:")
    print("1. Update mode (process new/changed tickets)")
    print("2. Initialization mode (process top tickets by child count)")
    print("3. Force refresh (reprocess all existing tickets)")
    print("4. Expansion/Limit mode (expand database to a specific number of tickets)")
    print("5. Resize mode (resize database to an exact number of tickets)")
    print("6. Test mode (simulate processing)")

    try:
        mode_choice = input("\nSelect mode (1-6): ").strip()
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled!")
        return 0

    # Initialize parameters
    init_mode = False
    force_refresh = False
    limit_tickets = None
    resize_tickets = None
    test_ticket = None

    # Configure parameters based on selected mode
    if mode_choice == '1':  # Update mode
        # No additional inputs required
        pass
    elif mode_choice == '2':  # Initialization mode
        init_mode = True
        try:
            limit_input = input("Enter ticket limit (or press Enter for no limit): ").strip()
            if limit_input.isdigit():
                limit_tickets = int(limit_input)
        except KeyboardInterrupt:
            print("\n\n👋 Operation cancelled!")
            return 0
    elif mode_choice == '3':  # Force refresh
        force_refresh = True
    elif mode_choice == '4':  # Expansion/Limit mode
        while limit_tickets is None:
            try:
                limit_input = input("Enter target number of tickets: ").strip()
                limit_tickets = int(limit_input)
                if limit_tickets < 0:
                    print("Please enter a non-negative number.")
                    limit_tickets = None
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\n\n👋 Operation cancelled!")
                return 0
    elif mode_choice == '5':  # Resize mode
        while resize_tickets is None:
            try:
                resize_input = input("Enter exact number of tickets to resize to: ").strip()
                resize_tickets = int(resize_input)
                if resize_tickets < 0:
                    print("Please enter a non-negative number.")
                    resize_tickets = None
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\n\n👋 Operation cancelled!")
                return 0
    elif mode_choice == '6':  # Test mode
        try:
            test_ticket = input("Enter ticket key to test: ").strip()
            if test_ticket:
                return _run_test_mode(config, logger, selected_bot, test_ticket)
            else:
                print("❌ Test ticket key required")
                return 1
        except KeyboardInterrupt:
            print("\n\n👋 Operation cancelled!")
            return 0
    else:
        print("❌ Invalid mode selection")
        return 1
    
    # Run the updater
    try:
        updater = FeedbackKnowledgeUpdater(config, logger, selected_bot, selected_summarizer)
        
        print(f"\n🚀 Starting updater...")
        print(f"Bot: {selected_bot}")
        print(f"Summarizer: {selected_summarizer}")
        print(f"Mode: {'Initialize' if init_mode else 'Force Refresh' if force_refresh else 'Update'}")
        if limit_tickets:
            print(f"Limit: {limit_tickets} tickets")
        
        result = updater.run_update(
            init_mode=init_mode,
            force_refresh=force_refresh,
            limit_tickets=limit_tickets,
            resize_tickets=resize_tickets,
            report_only_processed=True
        )
        
        # Display results
        print(f"\n✅ Update completed!")
        print(f"Total tickets found: {result['total_tickets']}")
        if result.get('resize_mode', False):
            print(f"Tickets added for resize: {result['resize_added']}")
            print(f"Tickets removed for resize: {result['resize_removed']}")
        elif result.get('expansion_mode', False):
            print(f"Tickets added for expansion: {result['expansion_added']}")
        else:
            print(f"New tickets processed: {result['new_processed']}")
        print(f"Updated tickets processed: {result['updated_processed']}")
        print(f"Total processed: {result['total_processed']}")
        print(f"Failed: {result['total_failed']}")
        print(f"Duration: {result['duration']}")
        if result.get('report_path'):
            print(f"Report: {result['report_path']}")
        return 0
        
    except Exception as e:
        logger.error(f"Error running updater: {e}")
        print(f"❌ Error: {e}")
        return 1


def _run_test_mode(config: Dict[str, Any], logger: logging.Logger, selected_bot: str, test_ticket: str) -> int:
    """Run test mode for a specific ticket"""
    try:
        updater = FeedbackKnowledgeUpdater(config, logger, selected_bot)
        
        print(f"\n🧪 Test mode: {test_ticket}")
        success = updater.test_child_count_change(test_ticket)
        
        if success:
            print("✅ Test completed successfully")
            print(f"💡 Now run update mode to see the simulated change processed")
            return 0
        else:
            print("❌ Test failed")
            return 1
            
    except Exception as e:
        logger.error(f"Error in test mode: {e}")
        print(f"❌ Error: {e}")
        return 1


def _test_jira_connection(config: Dict[str, Any], logger: logging.Logger) -> None:
    """Test JIRA connection"""
    print("\n=== JIRA Connection Test ===")
    
    try:
        from jira_integration.client import JiraClient
        
        jira_client = JiraClient(config, logger)
        
        if jira_client.test_connection():
            print("✅ JIRA connection successful!")
        else:
            print("❌ JIRA connection failed")
            
    except Exception as e:
        logger.error(f"JIRA connection test error: {e}")
        print(f"❌ JIRA connection error: {e}") 