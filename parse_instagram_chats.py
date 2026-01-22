#!/usr/bin/env python3
"""
Script to parse Instagram exported HTML files and extract chat messages.
"""

import re
import json
import os
from html import unescape
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

def convert_to_ist(timestamp_str):
    """
    Convert Instagram timestamp to IST (Indian Standard Time).
    Instagram exports appear to be in a timezone that's 13 hours 30 minutes behind IST.
    Example: 8:31 AM -> 10:01 PM IST
    """
    if not timestamp_str:
        return timestamp_str
    
    try:
        # Parse the timestamp (format: "May 28, 2025 8:31 am" or "Jan 16, 2026 4:08 am")
        # Try different formats
        formats = [
            "%b %d, %Y %I:%M %p",  # "May 28, 2025 8:31 am"
            "%B %d, %Y %I:%M %p",  # "January 16, 2026 4:08 am"
        ]
        
        dt = None
        for fmt in formats:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                break
            except ValueError:
                continue
        
        if dt is None:
            # If parsing fails, return original
            return timestamp_str
        
        # Add 13 hours 30 minutes to convert to IST
        dt_ist = dt + timedelta(hours=13, minutes=30)
        
        # Format back to the same format
        return dt_ist.strftime("%b %d, %Y %I:%M %p").replace(" 0", " ").replace("AM", "am").replace("PM", "pm")
    except Exception as e:
        print(f"Error converting timestamp '{timestamp_str}': {e}")
        return timestamp_str

def extract_messages_from_html(html_file_path):
    """Extract messages from an Instagram HTML file."""
    messages = []
    
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use BeautifulSoup to parse HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all message containers
        # Messages are in divs with class "pam _3-95 _2ph- _a6-g uiBoxWhite noborder"
        message_containers = soup.find_all('div', class_=lambda x: x and 'pam' in x and '_a6-g' in x)
        
        for container in message_containers:
            # Extract sender name
            sender_elem = container.find('h2', class_=lambda x: x and '_a6-h' in x)
            if not sender_elem:
                continue
            
            sender = sender_elem.get_text(strip=True)
            
            # Extract message content
            message_elem = container.find('div', class_=lambda x: x and '_a6-p' in x)
            if not message_elem:
                continue
            
            # Get all text content
            message_text = message_elem.get_text(separator=' ', strip=True)
            
            # Extract timestamp
            timestamp_elem = container.find('div', class_=lambda x: x and '_a6-o' in x)
            timestamp_raw = timestamp_elem.get_text(strip=True) if timestamp_elem else ""
            # Convert to IST
            timestamp = convert_to_ist(timestamp_raw)
            
            # Check if it's a sent message (from "You" or "साहील")
            is_sent = "You sent" in message_text or sender == "साहील" or "You" in sender
            
            # Extract reactions if any
            reactions = []
            reaction_elem = message_elem.find('ul', class_=lambda x: x and '_a6-q' in x)
            if reaction_elem:
                reaction_items = reaction_elem.find_all('li')
                for item in reaction_items:
                    reactions.append(item.get_text(strip=True))
            
            # Extract images
            images = []
            seen_images = set()  # Track to avoid duplicates
            
            # Look for img tags
            img_tags = message_elem.find_all('img', src=True)
            for img in img_tags:
                src = img.get('src', '')
                if src and 'photos' in src:
                    # Extract relative path to image
                    # Path format: your_instagram_activity/messages/inbox/hufrish_1697894724937506/photos/1579979189694141.jpg
                    # Get the folder name from the HTML file path
                    folder_name = os.path.basename(os.path.dirname(html_file_path))
                    # Extract just the filename
                    filename = src.split('/')[-1]
                    # Remove query parameters if any
                    filename = filename.split('?')[0]
                    # Avoid duplicates
                    image_key = f"{folder_name}/{filename}"
                    if image_key not in seen_images:
                        seen_images.add(image_key)
                        images.append({
                            'type': 'image',
                            'path': filename,  # Store just filename, we'll construct full path in JS
                            'folder': folder_name,
                            'alt': img.get('alt', '')
                        })
            
            # Extract attachments/links
            attachments = []
            links = message_elem.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                if href:
                    # Check if it's an image link
                    if 'photos' in href:
                        # Extract filename
                        filename = href.split('/')[-1]
                        filename = filename.split('?')[0]  # Remove query params
                        folder_name = os.path.basename(os.path.dirname(html_file_path))
                        image_key = f"{folder_name}/{filename}"
                        if image_key not in seen_images:
                            seen_images.add(image_key)
                            images.append({
                                'type': 'image',
                                'path': filename,
                                'folder': folder_name,
                                'alt': link.get_text(strip=True) or ''
                            })
                    elif 'instagram.com' in href or href.startswith('http'):
                        attachments.append({
                            'type': 'link',
                            'url': href,
                            'text': link.get_text(strip=True)
                        })
            
            # Skip system messages
            system_keywords = [
                'liked a message',
                'reacted',
                'Group invitation link',
                'Participants:',
                'sent an attachment'  # We'll extract the actual content below
            ]
            
            is_system = any(keyword in message_text.lower() for keyword in system_keywords)
            
            # Clean up message text (remove "You sent an attachment" etc.)
            if "sent an attachment" in message_text:
                # Try to get the actual content from nested divs
                # Look for divs that contain the actual post/reel content
                nested_divs = message_elem.find_all('div', recursive=True)
                actual_content = ""
                for div in nested_divs:
                    div_text = div.get_text(separator=' ', strip=True)
                    # Skip if it's just the "sent an attachment" text or username
                    if (div_text and 
                        "sent an attachment" not in div_text.lower() and
                        len(div_text) > 30 and  # Has substantial content
                        not div_text.startswith('http')):  # Not just a URL
                        actual_content = div_text
                        break
                
                if actual_content:
                    message_text = actual_content
                    is_system = False
                else:
                    # If no actual content found, keep the message but mark it as attachment-only
                    message_text = ""
            
            # Only add if it's not a pure system message or has actual content
            if not is_system and (message_text.strip() or attachments or reactions or images):
                messages.append({
                    'sender': sender,
                    'message': message_text.strip(),
                    'timestamp': timestamp,
                    'is_sent': is_sent,
                    'reactions': reactions,
                    'attachments': attachments,
                    'images': images
                })
    
    except Exception as e:
        print(f"Error parsing {html_file_path}: {e}")
        # Fallback to regex parsing
        return extract_messages_regex(html_file_path)
    
    return messages

def extract_messages_regex(html_file_path):
    """Fallback regex-based extraction."""
    messages = []
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match message blocks
    pattern = r'<h2[^>]*class="[^"]*_a6-h[^"]*"[^>]*>([^<]+)</h2>.*?<div[^>]*class="[^"]*_a6-p[^"]*"[^>]*>(.*?)</div>.*?<div[^>]*class="[^"]*_a6-o[^"]*"[^>]*>([^<]+)</div>'
    
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        sender = unescape(match.group(1).strip())
        message_html = match.group(2)
        timestamp_raw = match.group(3).strip()
        # Convert to IST
        timestamp = convert_to_ist(timestamp_raw)
        
        # Extract text from message HTML
        message_text = re.sub(r'<[^>]+>', ' ', message_html)
        message_text = ' '.join(message_text.split())
        message_text = unescape(message_text)
        
        is_sent = "You sent" in message_text or sender == "साहील" or "You" in sender
        
        if message_text or "sent an attachment" in message_html:
            messages.append({
                'sender': sender,
                'message': message_text,
                'timestamp': timestamp,
                'is_sent': is_sent,
                'reactions': [],
                'attachments': []
            })
    
    return messages

def get_chat_name(html_file_path):
    """Extract chat name from HTML title or first message."""
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to get from title tag
        title_match = re.search(r'<title>([^<]+)</title>', content)
        if title_match:
            return title_match.group(1).strip()
        
        # Try to get from header
        header_match = re.search(r'<h1[^>]*id="[^"]*"[^>]*>([^<]+)</h1>', content)
        if header_match:
            return header_match.group(1).strip()
    except:
        pass
    
    # Default to folder name
    return os.path.basename(os.path.dirname(html_file_path))

def main():
    """Main function to parse all chat files."""
    base_dir = "Instagram/your_instagram_activity/messages/inbox"
    
    chats = {
        'hufrish': {
            'folder': 'hufrish_1697894724937506',
            'name': 'HUFRISH',
            'messages': []
        },
        'smolexoticfish': {
            'folder': 'smolexoticfish_31077562368510029',
            'name': 'smol exotic fish 🤣🤣🤣',
            'messages': []
        }
    }
    
    for chat_key, chat_info in chats.items():
        folder_path = os.path.join(base_dir, chat_info['folder'])
        
        # Find all message HTML files
        message_files = []
        for i in range(1, 10):  # Check up to 10 message files
            msg_file = os.path.join(folder_path, f'message_{i}.html')
            if os.path.exists(msg_file):
                message_files.append(msg_file)
        
        # Parse all message files
        all_messages = []
        for msg_file in sorted(message_files):
            print(f"Parsing {msg_file}...")
            messages = extract_messages_from_html(msg_file)
            all_messages.extend(messages)
        
        # Get chat name from first file
        if message_files:
            chat_name = get_chat_name(message_files[0])
            chats[chat_key]['name'] = chat_name
        
        chats[chat_key]['messages'] = all_messages
        print(f"Extracted {len(all_messages)} messages from {chat_key}")
    
    # Save to JSON
    output_file = 'pookie/chats_data.json'
    os.makedirs('pookie', exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chats, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved chat data to {output_file}")
    print(f"Total messages: {len(chats['hufrish']['messages'])} + {len(chats['smolexoticfish']['messages'])}")

if __name__ == '__main__':
    main()
