from datetime import datetime, timedelta


def is_future_datetime(datetime_str, timezone_str=None):
    """
    Check if a datetime string represents a future date/time.
    
    Args:
        datetime_str (str): ISO format datetime string
        timezone_str (str, optional): Timezone string (currently not used)
    
    Returns:
        bool: True if the datetime is in the future, False otherwise
    
    Examples:
        >>> is_future_datetime("2025-06-02T10:00:00.0000000")
        True (assuming current date is before June 2, 2025)
        >>> is_future_datetime("2024-01-01T10:00:00Z")
        False (assuming current date is after January 1, 2024)
    """
    try:
        # Clean up the datetime string to handle Microsoft format with 7 decimal places
        clean_datetime_str = datetime_str
        
        # Handle Microsoft datetime format with 7 decimal places (e.g., .0000000)
        # Python's fromisoformat only supports up to 6 decimal places
        if '.0000000' in clean_datetime_str:
            clean_datetime_str = clean_datetime_str.replace('.0000000', '.000000')
        elif clean_datetime_str.count('.') == 1 and len(clean_datetime_str.split('.')[1].split('T')[0] if 'T' in clean_datetime_str.split('.')[1] else clean_datetime_str.split('.')[1]) > 6:
            # Handle any datetime with more than 6 decimal places
            parts = clean_datetime_str.split('.')
            if len(parts) == 2:
                # Find where the decimal part ends (before timezone info)
                decimal_part = parts[1]
                tz_part = ''
                for i, char in enumerate(decimal_part):
                    if char in '+-Z':
                        tz_part = decimal_part[i:]
                        decimal_part = decimal_part[:i]
                        break
                # Truncate to 6 decimal places
                if len(decimal_part) > 6:
                    decimal_part = decimal_part[:6]
                clean_datetime_str = parts[0] + '.' + decimal_part + tz_part
        
        # Parse the datetime string
        if clean_datetime_str.endswith('Z'):
            # UTC timezone
            dt = datetime.fromisoformat(clean_datetime_str.replace('Z', '+00:00'))
        elif any(tz_indicator in clean_datetime_str for tz_indicator in ['+', '-']) and ('T' in clean_datetime_str):
            # Has timezone info (check for + or - after T to avoid matching negative dates)
            # Additional check: make sure the timezone indicator appears after the 'T'
            t_index = clean_datetime_str.rfind('T')
            if t_index != -1 and ('+' in clean_datetime_str[t_index:] or '-' in clean_datetime_str[t_index:]):
                dt = datetime.fromisoformat(clean_datetime_str)
            else:
                # No timezone info, assume UTC
                dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
        else:
            # No timezone info, assume UTC
            dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
        
        # Compare with current UTC time
        current_utc = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.utcnow()
        return dt > current_utc
        
    except Exception as e:
        print(f"Error checking if datetime {datetime_str} is in future: {str(e)}")
        return False  # Default to False if we can't parse the date


def format_datetime_range_human_readable(start_datetime_str, end_datetime_str=None, default_duration_minutes=30, timezone_str=None):
    """
    Convert datetime strings to human-readable format with start and end times like 'June 2nd 3pm-3:30pm'
    
    Args:
        start_datetime_str (str): ISO format datetime string for start time
        end_datetime_str (str, optional): ISO format datetime string for end time. If not provided, 
                                        will add default_duration_minutes to start time
        default_duration_minutes (int): Default duration in minutes if end_datetime_str is not provided
        timezone_str (str, optional): Timezone string (currently not used)
    
    Returns:
        str: Human-readable datetime range format like 'June 2nd 3pm-3:30pm'
    
    Examples:
        >>> format_datetime_range_human_readable("2025-06-02T15:00:00.0000000", "2025-06-02T15:30:00.0000000")
        'June 2nd 3pm-3:30pm'
        >>> format_datetime_range_human_readable("2025-06-02T10:00:00Z")
        'June 2nd 10am-10:30am'
    """
    try:
        # Helper function to clean datetime string
        def clean_datetime_string(datetime_str):
            clean_datetime_str = datetime_str
            
            # Handle Microsoft datetime format with 7 decimal places (e.g., .0000000)
            if '.0000000' in clean_datetime_str:
                clean_datetime_str = clean_datetime_str.replace('.0000000', '.000000')
            elif clean_datetime_str.count('.') == 1 and len(clean_datetime_str.split('.')[1].split('T')[0] if 'T' in clean_datetime_str.split('.')[1] else clean_datetime_str.split('.')[1]) > 6:
                # Handle any datetime with more than 6 decimal places
                parts = clean_datetime_str.split('.')
                if len(parts) == 2:
                    # Find where the decimal part ends (before timezone info)
                    decimal_part = parts[1]
                    tz_part = ''
                    for i, char in enumerate(decimal_part):
                        if char in '+-Z':
                            tz_part = decimal_part[i:]
                            decimal_part = decimal_part[:i]
                            break
                    # Truncate to 6 decimal places
                    if len(decimal_part) > 6:
                        decimal_part = decimal_part[:6]
                    clean_datetime_str = parts[0] + '.' + decimal_part + tz_part
            
            return clean_datetime_str
        
        # Helper function to parse datetime
        def parse_datetime(datetime_str):
            clean_str = clean_datetime_string(datetime_str)
            
            if clean_str.endswith('Z'):
                # UTC timezone
                return datetime.fromisoformat(clean_str.replace('Z', '+00:00'))
            elif any(tz_indicator in clean_str for tz_indicator in ['+', '-']) and ('T' in clean_str):
                # Has timezone info
                t_index = clean_str.rfind('T')
                if t_index != -1 and ('+' in clean_str[t_index:] or '-' in clean_str[t_index:]):
                    return datetime.fromisoformat(clean_str)
                else:
                    # No timezone info, assume UTC
                    return datetime.fromisoformat(clean_str + '+00:00')
            else:
                # No timezone info, assume UTC
                return datetime.fromisoformat(clean_str + '+00:00')
        
        # Parse start datetime
        start_dt = parse_datetime(start_datetime_str)
        
        # Parse or calculate end datetime
        if end_datetime_str:
            end_dt = parse_datetime(end_datetime_str)
        else:
            end_dt = start_dt + timedelta(minutes=default_duration_minutes)
        
        # Get month name
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        month = month_names[start_dt.month - 1]
        
        # Get day with ordinal suffix
        day = start_dt.day
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        
        # Helper function to format time
        def format_time(dt):
            hour = dt.hour
            minute = dt.minute
            
            if hour == 0:
                time_str = '12am'
            elif hour < 12:
                time_str = f'{hour}am'
            elif hour == 12:
                time_str = '12pm'
            else:
                time_str = f'{hour - 12}pm'
            
            # Add minutes if not on the hour
            if minute != 0:
                time_str = time_str[:-2] + f':{minute:02d}' + time_str[-2:]
            
            return time_str
        
        start_time_str = format_time(start_dt)
        end_time_str = format_time(end_dt)
        
        return f'{month} {day}{suffix} {start_time_str}-{end_time_str}'
        
    except Exception as e:
        print(f"Error formatting datetime range {start_datetime_str} to {end_datetime_str}: {str(e)}")
        # Fallback to single time format
        return format_datetime_human_readable(start_datetime_str, timezone_str)


def format_datetime_human_readable(datetime_str, timezone_str=None):
    """
    Convert datetime string to human-readable format like 'June 2nd 4pm'
    
    Args:
        datetime_str (str): ISO format datetime string
        timezone_str (str, optional): Timezone string (currently not used)
    
    Returns:
        str: Human-readable datetime format like 'June 2nd 4pm'
    
    Examples:
        >>> format_datetime_human_readable("2025-06-02T10:00:00.0000000")
        'June 2nd 10am'
        >>> format_datetime_human_readable("2025-06-02T16:30:00Z")
        'June 2nd 4:30pm'
    """
    try:
        # Clean up the datetime string to handle Microsoft format with 7 decimal places
        clean_datetime_str = datetime_str
        
        # Handle Microsoft datetime format with 7 decimal places (e.g., .0000000)
        # Python's fromisoformat only supports up to 6 decimal places
        if '.0000000' in clean_datetime_str:
            clean_datetime_str = clean_datetime_str.replace('.0000000', '.000000')
        elif clean_datetime_str.count('.') == 1 and len(clean_datetime_str.split('.')[1].split('T')[0] if 'T' in clean_datetime_str.split('.')[1] else clean_datetime_str.split('.')[1]) > 6:
            # Handle any datetime with more than 6 decimal places
            parts = clean_datetime_str.split('.')
            if len(parts) == 2:
                # Find where the decimal part ends (before timezone info)
                decimal_part = parts[1]
                tz_part = ''
                for i, char in enumerate(decimal_part):
                    if char in '+-Z':
                        tz_part = decimal_part[i:]
                        decimal_part = decimal_part[:i]
                        break
                # Truncate to 6 decimal places
                if len(decimal_part) > 6:
                    decimal_part = decimal_part[:6]
                clean_datetime_str = parts[0] + '.' + decimal_part + tz_part
        
        # Parse the datetime string
        if clean_datetime_str.endswith('Z'):
            # UTC timezone
            dt = datetime.fromisoformat(clean_datetime_str.replace('Z', '+00:00'))
        elif any(tz_indicator in clean_datetime_str for tz_indicator in ['+', '-']) and ('T' in clean_datetime_str):
            # Has timezone info (check for + or - after T to avoid matching negative dates)
            # Additional check: make sure the timezone indicator appears after the 'T'
            t_index = clean_datetime_str.rfind('T')
            if t_index != -1 and ('+' in clean_datetime_str[t_index:] or '-' in clean_datetime_str[t_index:]):
                dt = datetime.fromisoformat(clean_datetime_str)
            else:
                # No timezone info, assume UTC
                dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
        else:
            # No timezone info, assume UTC
            dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
        
        # Get month name
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        month = month_names[dt.month - 1]
        
        # Get day with ordinal suffix
        day = dt.day
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        
        # Get time in 12-hour format
        hour = dt.hour
        if hour == 0:
            time_str = '12am'
        elif hour < 12:
            time_str = f'{hour}am'
        elif hour == 12:
            time_str = '12pm'
        else:
            time_str = f'{hour - 12}pm'
        
        # Add minutes if not on the hour
        if dt.minute != 0:
            time_str = time_str[:-2] + f':{dt.minute:02d}' + time_str[-2:]
        
        return f'{month} {day}{suffix} {time_str}'
        
    except Exception as e:
        print(f"Error formatting datetime {datetime_str}: {str(e)}")
        return datetime_str
