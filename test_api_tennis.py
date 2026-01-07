#!/usr/bin/env python3
"""
Test script to verify API-Tennis.com API key functionality.
"""

import requests
import sys
from datetime import datetime, timedelta
import json

def test_api_tennis(api_key: str, date: datetime = None):
    """
    Test API-Tennis.com API with provided key.
    
    Args:
        api_key: API key to test
        date: Date to test (default: yesterday)
    """
    if date is None:
        date = datetime.now() - timedelta(days=1)
    
    date_str = date.strftime('%Y-%m-%d')
    
    url = 'https://api.api-tennis.com/tennis/'
    params = {
        'method': 'get_fixtures',  # Updated to use get_fixtures per documentation
        'APIkey': api_key,
        'date_start': date_str,
        'date_stop': date_str,
        'event_type_key': '265'  # ATP Singles (266 for WTA Singles)
    }
    
    print(f'Testing API-Tennis.com')
    print(f'Date: {date_str}')
    print(f'URL: {url}')
    print('-' * 60)
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f'Status Code: {response.status_code}')
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f'✓ API responded successfully')
                print(f'Response keys: {list(data.keys()) if isinstance(data, dict) else "Not a dict"}')
                
                if isinstance(data, dict):
                    # Check for success field (per API-Tennis.com documentation)
                    if data.get('success') != 1:
                        print(f'✗ API Error: {data.get("error", "Request was not successful")}')
                        return False
                    
                    if 'result' in data:
                        results = data.get('result', [])
                        # Filter for completed matches (event_final_result != "-")
                        completed = [r for r in results if r.get('event_final_result', '') != '-']
                        print(f'Total fixtures: {len(results)}')
                        print(f'Completed matches: {len(completed)}')
                        if completed:
                            print(f'\nSample completed match (first):')
                            print(json.dumps(completed[0], indent=2))
                            return True
                        else:
                            print('⚠️  No completed matches found for this date')
                            return False
                    elif 'error' in data:
                        print(f'✗ API Error: {data.get("error")}')
                        return False
                    else:
                        print(f'⚠️  Unexpected response structure:')
                        print(json.dumps(data, indent=2)[:500])
                        return False
                else:
                    print(f'⚠️  Response is not a dictionary: {type(data)}')
                    return False
                    
            except json.JSONDecodeError as e:
                print(f'✗ Invalid JSON response: {e}')
                print(f'Response text: {response.text[:500]}')
                return False
        else:
            print(f'✗ HTTP Error {response.status_code}')
            print(f'Response: {response.text[:500]}')
            return False
            
    except requests.exceptions.Timeout:
        print('✗ Request timeout - API may be down')
        return False
    except requests.exceptions.RequestException as e:
        print(f'✗ Request failed: {e}')
        return False
    except Exception as e:
        print(f'✗ Unexpected error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    api_key = sys.argv[1] if len(sys.argv) > 1 else 'd2fbcb32f85c9d3243bc7017b2e95e095c69d3b553718659333548b230a40cd4'
    
    print('=' * 60)
    print('API-Tennis.com API Key Test')
    print('=' * 60)
    print()
    
    success = test_api_tennis(api_key)
    
    print()
    print('=' * 60)
    if success:
        print('✓ API key appears to be working')
    else:
        print('✗ API key test failed - API may be down or key invalid')
    print('=' * 60)
    
    sys.exit(0 if success else 1)

