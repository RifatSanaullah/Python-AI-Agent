from datetime import datetime, timedelta
import re

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # For Python < 3.9, fallback to pytz
    try:
        import pytz
        class ZoneInfo:
            def __init__(self, key):
                self.zone = pytz.timezone(key) if key != 'UTC' else pytz.UTC
            
            def __call__(self, key):
                return pytz.timezone(key) if key != 'UTC' else pytz.UTC
        
        ZoneInfo = ZoneInfo('UTC').__call__
    except ImportError:
        # Final fallback - create basic timezone from offset
        from datetime import timezone
        def ZoneInfo(key):
            if key == 'UTC':
                return timezone.utc
            # For other timezones, return UTC as fallback
            return timezone.utc


def parse_timezone_offset(timezone_str):
    """
    Parse timezone string like 'UTC-06:00' or 'UTC+05:30' to create a ZoneInfo compatible timezone.
    
    Args:
        timezone_str (str): Timezone string like 'UTC-06:00', 'UTC+05:30', or standard timezone names
    
    Returns:
        datetime.timezone: A timezone object
    """
    try:
        if not timezone_str or timezone_str == 'UTC':
            return ZoneInfo('UTC')
        
        # Handle standard timezone names first
        if timezone_str in ['EST', 'PST', 'MST', 'CST']:
            timezone_map = {
                'EST': 'America/New_York',
                'PST': 'America/Los_Angeles', 
                'MST': 'America/Denver',
                'CST': 'America/Chicago'
            }
            return ZoneInfo(timezone_map[timezone_str])
        
        # Handle UTC offset format like 'UTC-06:00' or 'UTC+05:30'
        pattern = r'UTC([+-])(\d{1,2}):(\d{2})'
        match = re.match(pattern, timezone_str)
        
        if match:
            sign = 1 if match.group(1) == '+' else -1
            hours = int(match.group(2))
            minutes = int(match.group(3))
            
            total_minutes = sign * (hours * 60 + minutes)
            offset = timedelta(minutes=total_minutes)
            
            # Create a fixed offset timezone
            from datetime import timezone
            return timezone(offset)
        
        # Try to parse as standard timezone name
        return ZoneInfo(timezone_str)
        
    except Exception as e:
        print(f"Error parsing timezone {timezone_str}: {str(e)}")
        return ZoneInfo('UTC')  # Default to UTC


def convert_utc_to_user_timezone(utc_datetime_str, user_timezone_str):
    """
    Convert UTC datetime string to user's timezone.
    
    Args:
        utc_datetime_str (str): UTC datetime string
        user_timezone_str (str): User's timezone like 'UTC-06:00'
    
    Returns:
        datetime: Datetime object in user's timezone
    """
    try:
        # Parse UTC datetime
        clean_datetime_str = utc_datetime_str
        
        # Handle Microsoft datetime format with 7 decimal places (e.g., .0000000)
        if '.0000000' in clean_datetime_str:
            clean_datetime_str = clean_datetime_str.replace('.0000000', '.000000')
        elif clean_datetime_str.count('.') == 1 and len(clean_datetime_str.split('.')[1].split('T')[0] if 'T' in clean_datetime_str.split('.')[1] else clean_datetime_str.split('.')[1]) > 6:
            # Handle any datetime with more than 6 decimal places
            parts = clean_datetime_str.split('.')
            if len(parts) == 2:
                decimal_part = parts[1]
                tz_part = ''
                for i, char in enumerate(decimal_part):
                    if char in '+-Z':
                        tz_part = decimal_part[i:]
                        decimal_part = decimal_part[:i]
                        break
                if len(decimal_part) > 6:
                    decimal_part = decimal_part[:6]
                clean_datetime_str = parts[0] + '.' + decimal_part + tz_part
        
        # Parse as UTC datetime
        if clean_datetime_str.endswith('Z'):
            utc_dt = datetime.fromisoformat(clean_datetime_str.replace('Z', '+00:00'))
        elif any(tz_indicator in clean_datetime_str for tz_indicator in ['+', '-']) and ('T' in clean_datetime_str):
            t_index = clean_datetime_str.rfind('T')
            if t_index != -1 and ('+' in clean_datetime_str[t_index:] or '-' in clean_datetime_str[t_index:]):
                utc_dt = datetime.fromisoformat(clean_datetime_str)
            else:
                utc_dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
        else:
            utc_dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
        
        # Convert to user's timezone
        user_tz = parse_timezone_offset(user_timezone_str)
        user_dt = utc_dt.astimezone(user_tz)
        
        return user_dt
        
    except Exception as e:
        print(f"Error converting UTC datetime {utc_datetime_str} to timezone {user_timezone_str}: {str(e)}")
        return None


def is_future_datetime(datetime_str, timezone_str=None, user_timezone_str=None):
    """
    Check if a datetime string represents a future date/time.
    
    Args:
        datetime_str (str): ISO format datetime string
        timezone_str (str, optional): Timezone string (currently not used)
        user_timezone_str (str, optional): User's timezone for comparison
    
    Returns:
        bool: True if the datetime is in the future, False otherwise
    
    Examples:
        >>> is_future_datetime("2025-06-02T10:00:00.0000000", user_timezone_str="UTC-06:00")
        True (assuming current date is before June 2, 2025)
        >>> is_future_datetime("2024-01-01T10:00:00Z", user_timezone_str="UTC-06:00")
        False (assuming current date is after January 1, 2024)
    """
    try:
        if user_timezone_str:
            # Convert to user's timezone and compare with user's local time
            user_dt = convert_utc_to_user_timezone(datetime_str, user_timezone_str)
            if not user_dt:
                return False
            
            # Get current time in user's timezone
            user_tz = parse_timezone_offset(user_timezone_str)
            current_user_time = datetime.now(user_tz)
            
            # Add a small buffer (5 minutes) to avoid conflicts with appointments that just started
            buffer_minutes = 5
            current_user_time_with_buffer = current_user_time.replace(second=0, microsecond=0) + timedelta(minutes=buffer_minutes)
            
            is_future = user_dt > current_user_time_with_buffer
            
            # print(f"    DateTime check (user timezone): {user_dt.isoformat()} > {current_user_time_with_buffer.isoformat()} = {is_future}")
            
            return is_future
        else:
            # Fallback to UTC comparison
            clean_datetime_str = datetime_str
            
            # Handle Microsoft datetime format with 7 decimal places (e.g., .0000000)
            if '.0000000' in clean_datetime_str:
                clean_datetime_str = clean_datetime_str.replace('.0000000', '.000000')
            elif clean_datetime_str.count('.') == 1 and len(clean_datetime_str.split('.')[1].split('T')[0] if 'T' in clean_datetime_str.split('.')[1] else clean_datetime_str.split('.')[1]) > 6:
                parts = clean_datetime_str.split('.')
                if len(parts) == 2:
                    decimal_part = parts[1]
                    tz_part = ''
                    for i, char in enumerate(decimal_part):
                        if char in '+-Z':
                            tz_part = decimal_part[i:]
                            decimal_part = decimal_part[:i]
                            break
                    if len(decimal_part) > 6:
                        decimal_part = decimal_part[:6]
                    clean_datetime_str = parts[0] + '.' + decimal_part + tz_part
            
            # Parse the datetime string
            if clean_datetime_str.endswith('Z'):
                dt = datetime.fromisoformat(clean_datetime_str.replace('Z', '+00:00'))
            elif any(tz_indicator in clean_datetime_str for tz_indicator in ['+', '-']) and ('T' in clean_datetime_str):
                t_index = clean_datetime_str.rfind('T')
                if t_index != -1 and ('+' in clean_datetime_str[t_index:] or '-' in clean_datetime_str[t_index:]):
                    dt = datetime.fromisoformat(clean_datetime_str)
                else:
                    dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
            else:
                dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
            
            # Compare with current UTC time
            current_utc = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.utcnow()
            
            # Add a small buffer (5 minutes)
            buffer_minutes = 5
            current_utc_with_buffer = current_utc.replace(second=0, microsecond=0) + timedelta(minutes=buffer_minutes)
            
            is_future = dt > current_utc_with_buffer
            
            print(f"    DateTime check (UTC): {dt.isoformat()} > {current_utc_with_buffer.isoformat()} = {is_future}")
            
            return is_future
        
    except Exception as e:
        print(f"Error checking if datetime {datetime_str} is in future: {str(e)}")
        return False  # Default to False if we can't parse the date


def format_datetime_range_human_readable(start_datetime_str, end_datetime_str=None, default_duration_minutes=30, timezone_str=None, user_timezone_str=None):
    """
    Convert datetime strings to human-readable format with start and end times like 'June 2nd 3pm-3:30pm'
    
    Args:
        start_datetime_str (str): ISO format datetime string for start time
        end_datetime_str (str, optional): ISO format datetime string for end time. If not provided, 
                                        will add default_duration_minutes to start time
        default_duration_minutes (int): Default duration in minutes if end_datetime_str is not provided
        timezone_str (str, optional): Timezone string (currently not used)
        user_timezone_str (str, optional): User's timezone like 'UTC-06:00' for conversion
    
    Returns:
        str: Human-readable datetime range format like 'June 2nd 3pm-3:30pm'
    
    Examples:
        >>> format_datetime_range_human_readable("2025-06-02T15:00:00.0000000", "2025-06-02T15:30:00.0000000", user_timezone_str="UTC-06:00")
        'June 2nd 9am-9:30am'  # Converted from UTC to UTC-06:00
        >>> format_datetime_range_human_readable("2025-06-02T10:00:00Z", user_timezone_str="UTC+05:30")
        'June 2nd 3:30pm-4pm'  # Converted from UTC to UTC+05:30
    """
    try:
        if user_timezone_str:
            # Convert UTC times to user's timezone
            start_dt = convert_utc_to_user_timezone(start_datetime_str, user_timezone_str)
            if not start_dt:
                return format_datetime_range_human_readable(start_datetime_str, end_datetime_str, default_duration_minutes, timezone_str, None)
            
            if end_datetime_str:
                end_dt = convert_utc_to_user_timezone(end_datetime_str, user_timezone_str)
                if not end_dt:
                    end_dt = start_dt + timedelta(minutes=default_duration_minutes)
            else:
                end_dt = start_dt + timedelta(minutes=default_duration_minutes)
        else:
            # Fallback to original UTC parsing
            def clean_datetime_string(datetime_str):
                clean_datetime_str = datetime_str
                
                # Handle Microsoft datetime format with 7 decimal places (e.g., .0000000)
                if '.0000000' in clean_datetime_str:
                    clean_datetime_str = clean_datetime_str.replace('.0000000', '.000000')
                elif clean_datetime_str.count('.') == 1 and len(clean_datetime_str.split('.')[1].split('T')[0] if 'T' in clean_datetime_str.split('.')[1] else clean_datetime_str.split('.')[1]) > 6:
                    parts = clean_datetime_str.split('.')
                    if len(parts) == 2:
                        decimal_part = parts[1]
                        tz_part = ''
                        for i, char in enumerate(decimal_part):
                            if char in '+-Z':
                                tz_part = decimal_part[i:]
                                decimal_part = decimal_part[:i]
                                break
                        if len(decimal_part) > 6:
                            decimal_part = decimal_part[:6]
                        clean_datetime_str = parts[0] + '.' + decimal_part + tz_part
                
                return clean_datetime_str
            
            def parse_datetime(datetime_str):
                clean_str = clean_datetime_string(datetime_str)
                
                if clean_str.endswith('Z'):
                    return datetime.fromisoformat(clean_str.replace('Z', '+00:00'))
                elif any(tz_indicator in clean_str for tz_indicator in ['+', '-']) and ('T' in clean_str):
                    t_index = clean_str.rfind('T')
                    if t_index != -1 and ('+' in clean_str[t_index:] or '-' in clean_str[t_index:]):
                        return datetime.fromisoformat(clean_str)
                    else:
                        return datetime.fromisoformat(clean_str + '+00:00')
                else:
                    return datetime.fromisoformat(clean_str + '+00:00')
            
            start_dt = parse_datetime(start_datetime_str)
            
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
        
        # Add timezone info if user timezone is specified
        # timezone_info = ""
        # if user_timezone_str and user_timezone_str != 'UTC':
        #     timezone_info = f" {user_timezone_str}"
        
        return f'{month} {day}{suffix} ({start_time_str} to {end_time_str})'
        
    except Exception as e:
        print(f"Error formatting datetime range {start_datetime_str} to {end_datetime_str}: {str(e)}")
        # Fallback to single time format
        return format_datetime_human_readable(start_datetime_str, timezone_str, user_timezone_str)


def format_datetime_human_readable(datetime_str, timezone_str=None, user_timezone_str=None):
    """
    Convert datetime string to human-readable format like 'June 2nd 4pm'
    
    Args:
        datetime_str (str): ISO format datetime string
        timezone_str (str, optional): Timezone string (currently not used)
        user_timezone_str (str, optional): User's timezone like 'UTC-06:00' for conversion
    
    Returns:
        str: Human-readable datetime format like 'June 2nd 4pm'
    
    Examples:
        >>> format_datetime_human_readable("2025-06-02T10:00:00.0000000", user_timezone_str="UTC-06:00")
        'June 2nd 4am'  # Converted from UTC to UTC-06:00
        >>> format_datetime_human_readable("2025-06-02T16:30:00Z", user_timezone_str="UTC+05:30")
        'June 2nd 10pm'  # Converted from UTC to UTC+05:30
    """
    try:
        if user_timezone_str:
            # Convert UTC time to user's timezone
            dt = convert_utc_to_user_timezone(datetime_str, user_timezone_str)
            if not dt:
                return format_datetime_human_readable(datetime_str, timezone_str, None)
        else:
            # Fallback to original UTC parsing
            clean_datetime_str = datetime_str
            
            # Handle Microsoft datetime format with 7 decimal places (e.g., .0000000)
            if '.0000000' in clean_datetime_str:
                clean_datetime_str = clean_datetime_str.replace('.0000000', '.000000')
            elif clean_datetime_str.count('.') == 1 and len(clean_datetime_str.split('.')[1].split('T')[0] if 'T' in clean_datetime_str.split('.')[1] else clean_datetime_str.split('.')[1]) > 6:
                parts = clean_datetime_str.split('.')
                if len(parts) == 2:
                    decimal_part = parts[1]
                    tz_part = ''
                    for i, char in enumerate(decimal_part):
                        if char in '+-Z':
                            tz_part = decimal_part[i:]
                            decimal_part = decimal_part[:i]
                            break
                    if len(decimal_part) > 6:
                        decimal_part = decimal_part[:6]
                    clean_datetime_str = parts[0] + '.' + decimal_part + tz_part
            
            # Parse the datetime string
            if clean_datetime_str.endswith('Z'):
                dt = datetime.fromisoformat(clean_datetime_str.replace('Z', '+00:00'))
            elif any(tz_indicator in clean_datetime_str for tz_indicator in ['+', '-']) and ('T' in clean_datetime_str):
                t_index = clean_datetime_str.rfind('T')
                if t_index != -1 and ('+' in clean_datetime_str[t_index:] or '-' in clean_datetime_str[t_index:]):
                    dt = datetime.fromisoformat(clean_datetime_str)
                else:
                    dt = datetime.fromisoformat(clean_datetime_str + '+00:00')
            else:
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
        
        # Add timezone info if user timezone is specified
        timezone_info = ""
        if user_timezone_str and user_timezone_str != 'UTC':
            timezone_info = f" {user_timezone_str}"
        
        return f'{month} {day}{suffix} {time_str}{timezone_info}'
        
    except Exception as e:
        print(f"Error formatting datetime {datetime_str}: {str(e)}")
        return datetime_str


def sort_and_group_appointments(appointments_str: str) -> str:
    """
    Sort and group appointments by date.
    
    Args:
        appointments_str: String containing appointments separated by commas
        
    Returns:
        Sorted and grouped appointments string
    """
    if not appointments_str:
        return ""
        
    # Split into individual appointments
    appointments = [apt.strip() for apt in appointments_str.split(',')]
    
    # Parse appointments into structured data for sorting
    parsed_appointments = []
    for apt in appointments:
        try:
            # Extract date and time parts
            # Example format: "June 29th (2pm to 2:30pm UTC-05:00)"
            date_part = apt[:apt.find('(')].strip()
            time_part = apt[apt.find('('):].strip()
            
            # Parse month and day
            month = date_part.split()[0]  # June
            day = int(''.join(filter(str.isdigit, date_part.split()[1])))  # 29 from 29th
            
            # Convert month to number for sorting
            months = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                'September': 9, 'October': 10, 'November': 11, 'December': 12
            }
            month_num = months[month]
            
            # Parse time for secondary sorting
            time_str = time_part[1:time_part.find(' UTC')].lower()  # "2pm to 2:30pm"
            start_time = time_str.split(' to ')[0]  # "2pm"
            
            # Convert time to 24-hour format for sorting
            hour = int(''.join(filter(str.isdigit, start_time[:-2])))
            if start_time.endswith('pm') and hour != 12:
                hour += 12
            elif start_time.endswith('am') and hour == 12:
                hour = 0
                
            parsed_appointments.append({
                'original': apt,
                'sort_key': (month_num, day, hour),
                'month': month,
                'day': day
            })
        except Exception as e:
            print(f"Error parsing appointment: {apt} - {str(e)}")
            continue
    
    # Sort appointments
    parsed_appointments.sort(key=lambda x: x['sort_key'])
    
    # Group by date and join
    current_date = None
    grouped_appointments = []
    current_group = []
    
    for apt in parsed_appointments:
        date_key = (apt['month'], apt['day'])
        
        if date_key != current_date:
            if current_group:
                grouped_appointments.append(', '.join(current_group))
            current_group = [apt['original']]
            current_date = date_key
        else:
            current_group.append(apt['original'])
            
    # Add the last group
    if current_group:
        grouped_appointments.append(', '.join(current_group))
    
    return ', '.join(grouped_appointments)
