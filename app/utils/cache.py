"""
Cache management utilities
"""
from datetime import datetime
from config import Config
from app.extensions import cache


def get_cached_or_fetch(cache_key, fetch_function):
    """
    Get data from cache or fetch if expired
    
    Args:
        cache_key: Key to identify cached data
        fetch_function: Function to call if cache is expired
        
    Returns:
        Cached or freshly fetched data
    """
    now = datetime.now()
    cached = cache.get(cache_key)
    
    if cached and cached['data'] is not None and cached['timestamp'] is not None:
        age = (now - cached['timestamp']).total_seconds()
        if age < Config.CACHE_TTL:
            return cached['data']
    
    # Fetch fresh data
    try:
        data = fetch_function()
        cache[cache_key] = {'data': data, 'timestamp': now}
        return data
    except Exception as e:
        print(f"Error fetching {cache_key}: {e}")
        # Return cached data even if expired, or empty list
        return cached['data'] if cached and cached['data'] is not None else []


def invalidate_cache(*cache_keys):
    """
    Invalidate one or more cache entries
    
    Args:
        *cache_keys: Variable number of cache keys to invalidate
    """
    for key in cache_keys:
        if key in cache:
            cache[key] = {'data': None, 'timestamp': None}