
from datetime import datetime, timedelta


def extract_range(file_name : str):
    '''
    Extract the range of the download file from its name.

            Parameters:
                    file_name (str) : Name of file from which the range will be extracted

            Returns:
                    (start: datetime, end: datetime)
    '''
    quarter = False
    # preparation of name
    file_name = file_name.strip('Wetterstation_R.-Steiner-Schule_Ismaning_')
    file_name_segments = file_name.split('_')
    start_date = file_name_segments[0].split('-')
    start_time = file_name_segments[1].split('-')
    file_range = file_name_segments[2] + ' ' + file_name_segments[3]
    # start date
    start = datetime(
        int('20' + start_date[2]),
        int(start_date[1]),
        int(start_date[0]),
        int(start_time[0]),
        int(start_time[1]))
    if start.minute%30 == 15:
        start += timedelta(minutes=15)
        quarter = True
    # file range => end date
    end = None
    match file_range:
        case '1 Hour':
            end = start + timedelta(hours=1)
            if quarter:
                end -= timedelta(minutes=30)
        case '4 Hours':
            end = start + timedelta(hours=4)
            if quarter:
                end -= timedelta(minutes=30)
        case '8 Hours':
            end = start + timedelta(hours=8)
            if quarter:
                end -= timedelta(minutes=30)
        case '1 Day':
            end = start + timedelta(days=1)
        case '3 Day':
            end = start + timedelta(days=3)
        case '1 Week':
            end = start + timedelta(days=7)
        case '2 Week':
            end = start + timedelta(days=14)
        case '1 Month':
            end_month = start.month+1
            if end_month >= 13:
                end_month = 1
            current = start
            while current.month != end_month:
                current += timedelta(days=1)
            while current.day != start.day:
                current += timedelta(minutes=30)
            end = current
        case '3 Month':
            end_month = start.month+3
            if end_month >= 13:
                end_month = 1
            current = start
            while current.month != end_month:
                current += timedelta(days=1)
            while current.day != start.day:
                current += timedelta(minutes=30)
            end = current
        case '6 Month':
            end_month = start.month+6
            if end_month >= 13:
                end_month = 1
            current = start
            while current.month != end_month:
                current += timedelta(days=1)
            while current.day != start.day:
                current += timedelta(minutes=30)
            end = current
        case '1 Year':
            end_year = start.year+1
            current = start
            while current.year != end_year:
                current += timedelta(days=1)
            while current.month != start.month:
                current += timedelta(days=1)
            while current.day != start.day:
                current += timedelta(days=1)
                if current.month > start.month:
                    break
            end = current
    return (start, end)
