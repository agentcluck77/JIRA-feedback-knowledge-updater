#!/usr/bin/env python3
"""
Feedback Knowledge Updater - Main Entry Point
Refactored modular version of the feedback knowledge base maintenance tool.

Usage:
    python main.py                                                    # Interactive mode
    python main.py --list-bots                                        # List all available bots
    python main.py --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT    # Update mode with specific bots
    python main.py --init --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT      # Initialize with specific bots
    python main.py --init --limit 50 --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT  # Initialize with top 50 tickets
    python main.py --limit 200 --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT  # Expand database to 200 tickets
    python main.py --resize 50 --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT        # Resize to exactly 50 tickets
    python main.py --force-refresh --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT    # Refresh all existing tickets
    python main.py --all-tickets --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT      # Include all tickets in summary report
    python main.py --test-update TICKET_KEY --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT  # Test mode
"""

import argparse
import logging

from config.settings import load_config
from config.bot_config import list_available_classifier_bots, validate_classifier_bot_selection, list_available_summarizer_bots, validate_summarizer_bot_selection
from core.updater import FeedbackKnowledgeUpdater
from ui.interactive import run_interactive


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


def main():
    """Main entry point with command-line interface"""
    
    parser = argparse.ArgumentParser(
        description='Feedback Knowledge Updater - SeaTalk feedback knowledge base maintenance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                                    # Interactive mode
  python main.py --list-bots                                        # List all available bots
  python main.py --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT    # Update mode with specific bots
  python main.py --init --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT      # Initialize with specific bots
  python main.py --init --limit 50 --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT  # Initialize with top 50 tickets
  python main.py --limit 200 --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT  # Expand database to 200 tickets
  python main.py --resize 50 --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT        # Resize to exactly 50 tickets
  python main.py --force-refresh --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT    # Refresh all existing tickets
  python main.py --all-tickets --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT      # Include all tickets in summary report
  python main.py --test-update TICKET_KEY --classifier-bot CLASSIFIER_BOT --summarizer-bot SUMMARIZER_BOT  # Test mode
        """
    )
    
    parser.add_argument('--init', action='store_true', 
                       help='Initialize mode: process tickets prioritized by child count (ignores existing database)')
    parser.add_argument('--force-refresh', action='store_true',
                       help='Force refresh all existing tickets')
    parser.add_argument('--limit', type=int, metavar='N',
                       help='Limit processing to N tickets. In INIT mode: process top N tickets. In UPDATE mode: expand database to N tickets if needed.')
    parser.add_argument('--resize', type=int, metavar='N',
                       help='Resize classifier bot knowledge base to exactly N tickets (add/remove as needed to reach target size)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--all-tickets', action='store_true',
                       help='Include all tickets in summary report, not just processed ones')
    parser.add_argument('--test-update', metavar='TICKET_KEY',
                       help='Test mode: simulate child count change for specified ticket')
    parser.add_argument('--classifier-bot', metavar='BOT_NAME',
                       help='Specify which classifier bot to use (required unless --list-bots is used or in interactive mode)')
    parser.add_argument('--summarizer-bot', metavar='BOT_NAME', default='default',
                       help='Specify which summarizer bot to use (required: "default" or "alpha_summarizer")')
    parser.add_argument('--list-bots', action='store_true',
                       help='List all available classifier bots and exit')
    parser.add_argument('--interactive', action='store_true',
                       help='Run in interactive mode')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(log_level)
    
    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1
    
    # Handle --list-bots command
    if args.list_bots:
        print("Available bots:")
        print("="*50)
        
        # List classifier bots
        classifier_bots = list_available_classifier_bots()
        if classifier_bots:
            print("\nClassifier bots:")
            for bot_info in classifier_bots:
                print(f"  - {bot_info['display']}")
        else:
            print("\nNo classifier bots configured.")
        
        # List summarizer bots
        summarizer_bots = list_available_summarizer_bots()
        if summarizer_bots:
            print("\nSummarizer bots:")
            for bot_info in summarizer_bots:
                print(f"  - {bot_info['display']}")
        else:
            print("\nNo summarizer bots configured.")
        
        print(f"\nUsage:")
        print(f"  python main.py --classifier-bot <classifier_name> --summarizer-bot <summarizer_name>")
        print(f"  python main.py --classifier-bot <classifier_name>  # Uses 'default' summarizer")
        
        if not classifier_bots:
            print("\nTo configure classifier bots:")
            print("Please set CLASSIFIER_BOTS_CONFIG environment variable with JSON configuration,")
            print("or use interactive mode to configure bots.")
        
        if not summarizer_bots:
            print("\nTo configure summarizer bots:")
            print("Create and edit summarizer_bots_config.json file")
        
        return 0
    
    # Check if we should run in interactive mode
    # If no arguments provided or --interactive flag is set, use interactive mode
    if args.interactive or (not any([
            args.init, args.force_refresh, args.limit is not None, args.resize is not None, 
            args.test_update, args.classifier_bot, args.all_tickets
        ])):
        try:
            return run_interactive(logger)
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            return 0
    
    # Validate classifier bot selection for non-interactive mode
    if not args.classifier_bot and not args.test_update:
        available_bots = list_available_classifier_bots()
        if available_bots:
            print("❌ Error: --classifier-bot argument is required in non-interactive mode.")
            print("\nAvailable classifier bots:")
            for bot_info in available_bots:
                print(f"  - {bot_info['display']}")
            print(f"\nUsage: python main.py --classifier-bot <bot_name> [other_options]")
            print("Or use: python main.py --list-bots")
            print("Or run without arguments for interactive mode")
        else:
            print("❌ Error: No classifier bots configured.")
            print("Please set CLASSIFIER_BOTS_CONFIG environment variable with JSON configuration,")
            print("or use interactive mode to configure bots.")
            print("Example:")
            print('CLASSIFIER_BOTS_CONFIG=\'{"bot1": {"url": "...", "app_id": "...", "user_email": "..."}, "bot2": {...}}\'')
        return 1
    
    # Validate selected bots exist (skip for test mode without classifier operations)
    if args.classifier_bot:
        try:
            validate_classifier_bot_selection(config, args.classifier_bot)
            logger.info(f"Selected classifier bot: {args.classifier_bot}")
        except Exception as e:
            logger.error(f"Invalid classifier bot selection: {e}")
            return 1
    
    # Validate summarizer bot selection
    if args.summarizer_bot:
        try:
            validate_summarizer_bot_selection(args.summarizer_bot)
            logger.info(f"Selected summarizer bot: {args.summarizer_bot}")
        except Exception as e:
            logger.error(f"Invalid summarizer bot selection: {e}")
            return 1
    
    # Check if secrets are available in config files
    from config.bot_config import get_summarizer_bot_config, merge_classifier_bot_configs
    
    # Check summarizer bot configuration
    summarizer_config = get_summarizer_bot_config(args.summarizer_bot)
    if summarizer_config:
        if summarizer_config.get('bot_type') == 'ai_bot_platform' and not summarizer_config.get('app_secret'):
            logger.warning(f"Summarizer bot '{args.summarizer_bot}' missing app_secret - using fallback mode")
    
    # Check classifier bot configuration
    if args.classifier_bot:
        classifier_configs = merge_classifier_bot_configs()
        classifier_config = classifier_configs.get(args.classifier_bot)
        if classifier_config:
            if classifier_config.get('bot_type') == 'ai_bot_platform' and not classifier_config.get('app_secret'):
                logger.warning(f"Classifier bot '{args.classifier_bot}' missing app_secret - integration may be limited")
    
    # Run the updater
    try:
        updater = FeedbackKnowledgeUpdater(config, logger, args.classifier_bot, args.summarizer_bot)
        
        # Handle test mode if specified
        if args.test_update:
            logger.info(f"TEST MODE: Simulating child count change for ticket {args.test_update}")
            success = updater.test_child_count_change(args.test_update)
            if success:
                logger.info(f"TEST MODE: Successfully simulated child count change for {args.test_update}")
                logger.info(f"TEST MODE: Now run 'python main.py --limit 5 --classifier-bot {args.classifier_bot or '<bot_name>'}' to test the update process")
                return 0
            else:
                logger.error(f"TEST MODE: Failed to simulate child count change for {args.test_update}")
                return 1
        
        result = updater.run_update(
            init_mode=args.init,
            force_refresh=args.force_refresh,
            limit_tickets=args.limit,
            resize_tickets=args.resize,
            report_only_processed=not args.all_tickets
        )
        
        # Print summary
        print("\n" + "="*60)
        print("FEEDBACK KNOWLEDGE UPDATER - EXECUTION SUMMARY")
        print("="*60)
        mode_name = 'INITIALIZATION' if args.init else ('RESIZE' if result.get('resize_mode', False) else ('EXPANSION' if result.get('expansion_mode', False) else 'UPDATE'))
        print(f"Mode: {mode_name}")
        if args.classifier_bot:
            print(f"Classifier Bot: {args.classifier_bot}")
        print(f"Total tickets found: {result['total_tickets']}")
        
        if result.get('resize_mode', False):
            print(f"Tickets added for resize: {result['resize_added']}")
            print(f"Existing tickets updated: {result['updated_processed']}")
        elif result.get('expansion_mode', False):
            print(f"Tickets added for expansion: {result['expansion_added']}")
            print(f"Existing tickets updated: {result['updated_processed']}")
        else:
            print(f"New tickets processed: {result['new_processed']}")
        print(f"Updated tickets processed: {result['updated_processed']}")
            
        print(f"Total processed: {result['total_processed']}")
        print(f"Failed: {result['total_failed']}")
        print(f"Duration: {result['duration']}")
        # print(f"Report generated: {result['report_path']}")
        print("="*60)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        print("\n\n👋 Operation cancelled. Goodbye!")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    exit(main()) 