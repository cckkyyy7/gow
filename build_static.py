import os
import json
import pandas as pd
from app import app, get_stats, home

# Create directories
os.makedirs('static/data', exist_ok=True)

# 1. Generate JSON Data
print("Generating static data...")

# Stats & History
with app.app_context():
    # Since get_stats returns a Response object (jsonify), we need to extract data
    # But get_stats logic in app.py reads from CSV.
    # We can just reuse the logic or replicate it. 
    # Let's replicate reading to ensure clean JSON dump.
    
    data_file = 'fund_data.csv'
    stats = {}
    history = []
    
    if os.path.exists(data_file):
        df = pd.read_csv(data_file)
        if not df.empty:
            last_row = df.iloc[-1]
            stats = {
                'daily_hpr': last_row['daily_hpr'],
                'prev_daily_hpr': 0.0, # Mock or calc
                'monthly_hpr': last_row['monthly_hpr'],
                'prev_monthly_hpr': 0.0,
                'yearly_hpr': last_row['yearly_hpr'],
                'prev_yearly_hpr': 0.0
            }
            # History
            history = df.to_dict('records')
    
    with open('static/data/stats.json', 'w') as f:
        json.dump(stats, f)
        
    with open('static/data/history.json', 'w') as f:
        json.dump(history, f)

# Comparison Data
compare_file = 'compare.csv'
comparison_data = {}
if os.path.exists(compare_file):
    df_comp = pd.read_csv(compare_file)
    comparison_data = {
        'headers': df_comp.columns.tolist(),
        'rows': df_comp.to_dict('records')
    }

with open('static/data/comparison.json', 'w') as f:
    json.dump(comparison_data, f)

print("Data generated in static/data/")

# 2. Render HTML
# We can just copy templates/index.html to index.html if there's no Jinja2 usage
# But app.py uses render_template.
# Let's render it through Flask to be safe (though index.html seems static).
with app.test_request_context():
    rendered_html = home()
    # If home() returns a string (rendered html), good. 
    # If it returns a Response object, we get .data.
    # app.py: return render_template('index.html') -> returns string usually.
    
    with open('index.html', 'w') as f:
        f.write(rendered_html)

print("index.html generated.")
