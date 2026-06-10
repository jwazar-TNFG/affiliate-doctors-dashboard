#!/usr/bin/env python3
"""
Refresh affiliate doctors dashboard data from Supabase.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.supabase_client import get_client

# Define affiliate groupings
AFFILIATE_GROUPS = {
    'Georgia Injury Centers': {
        'keywords': ['georgia injury', 'gic'],
        'state': 'Georgia',
        'goal': 200
    },
    'Illinois Orthopedic Network (ION)': {
        'keywords': ['ion', 'illinois orthopedic'],
        'state': 'Illinois',
        'goal': 100
    },
    'Physicians Group / Path Medical': {
        'keywords': ['physicians group', 'path medical', 'ask gary'],
        'state': 'Florida',
        'goal': 0
    },
    'Arrowhead Clinics': {
        'keywords': ['arrowhead'],
        'state': 'Georgia',
        'goal': 51
    },
    'Hess Orthopedics (NJ)': {
        'keywords': ['hess'],
        'state': 'New Jersey',
        'goal': 25,
        'exclude': ['ny']
    },
    'Dr. Khan (FL)': {
        'keywords': ['khan'],
        'state': 'Florida',
        'goal': 50,
        'exclude': ['tx', 'dallas', 'texas']
    },
    'Dr. Genao': {
        'keywords': ['genao'],
        'state': 'Florida',
        'goal': 15
    },
    'Dr. Nalley': {
        'keywords': ['nalley'],
        'state': 'Florida',
        'goal': 5
    },
    'Neal': {
        'keywords': ['neal'],
        'state': 'Florida',
        'goal': 2
    },
    'Victor Patel': {
        'keywords': ['victor patel'],
        'state': 'Florida',
        'goal': 25
    }
}

# Exclusions
EXCLUDE_KEYWORDS = ['cor ', 'cor-', 'referred', 'workers comp', 'alpha']

def get_group(loc):
    """Map a treatment location to an affiliate group."""
    loc_lower = loc.lower()
    
    # Check exclusions first
    if any(x in loc_lower for x in EXCLUDE_KEYWORDS):
        return None
    
    for group_name, config in AFFILIATE_GROUPS.items():
        # Check if location matches keywords
        if any(kw in loc_lower for kw in config['keywords']):
            # Check excludes
            if 'exclude' in config:
                if any(ex in loc_lower for ex in config['exclude']):
                    continue
            return group_name
    
    return None

def refresh_data():
    """Refresh affiliate doctors data."""
    script_dir = Path(__file__).parent
    data_file = script_dir / 'data.json'
    
    sb = get_client()
    now = datetime.now()
    
    # Get current month date range
    start_date = now.strftime('%Y-%m-01')
    if now.month == 12:
        end_date = f"{now.year + 1}-01-01"
    else:
        end_date = f"{now.year}-{now.month + 1:02d}-01"
    
    print(f"Refreshing data for {now.strftime('%B %Y')}")
    print(f"Date range: {start_date} to {end_date}")
    
    # Fetch all treatment locations for current month
    all_data = []
    offset = 0
    batch_size = 1000
    
    while True:
        result = sb.table("rep_logs").select("txlocation") \
            .gte("idot", start_date) \
            .lt("idot", end_date) \
            .not_.is_("txlocation", "null") \
            .range(offset, offset + batch_size - 1) \
            .execute()
        
        all_data.extend(result.data)
        
        if len(result.data) < batch_size:
            break
        offset += batch_size
    
    print(f"Found {len(all_data)} treatment records")
    
    # Count by affiliate group
    group_counts = defaultdict(int)
    for r in all_data:
        loc = r.get('txlocation', '')
        group = get_group(loc)
        if group:
            group_counts[group] += 1
    
    # Build output data
    output_data = []
    for group_name, config in AFFILIATE_GROUPS.items():
        count = group_counts.get(group_name, 0)
        goal = config['goal']
        output_data.append({
            'clinic_name': group_name,
            'state': config['state'],
            'monthly_goal': goal,
            'gross': count,
            'net': count,
            'owed': max(0, goal - count),
            'percent': round(count / goal * 100) if goal > 0 else 0
        })
    
    # Sort by owed (descending)
    output_data.sort(key=lambda x: -x['owed'])
    
    # Build final JSON
    output = {
        'updated': now.strftime('%Y-%m-%dT%H:%M:%S'),
        'month': now.strftime('%B %Y'),
        'data': output_data
    }
    
    with open(data_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Updated {data_file}")
    
    # Summary
    total_goal = sum(d['monthly_goal'] for d in output_data)
    total_net = sum(d['net'] for d in output_data)
    print(f"Total: {total_net} / {total_goal} ({round(total_net/total_goal*100) if total_goal > 0 else 0}%)")

if __name__ == '__main__':
    refresh_data()
