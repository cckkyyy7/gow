from flask import Flask, render_template, jsonify, send_file
import pandas as pd
import os
from hpr_calculator import DATA_FILE

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    """Returns the latest stats from the CSV."""
    if not os.path.exists(DATA_FILE):
        return jsonify({
            'daily_hpr': 0,
            'prev_daily_hpr': 0,
            'monthly_hpr': 0,
            'prev_monthly_hpr': 0,
            'yearly_hpr': 0,
            'prev_yearly_hpr': 0
        })
        
    try:
        df = pd.read_csv(DATA_FILE)
        if df.empty:
             return jsonify({})
             
        latest = df.iloc[-1]
        
        # Calculate 'vs previous' for display
        # Previous Day
        if len(df) > 1:
            prev = df.iloc[-2]
            prev_daily_hpr = prev['daily_hpr']
            # For monthly comparision, we ideally compare to last month end? 
            # Or just vs yesterday's value of monthly HPR (which shows trend)?
            # The prompt says: "+24% vs Prev Month". This usually means compare current Month HPR 
            # to the FINAL Month HPR of the previous month.
            
            # Simple approximation for demo: Compare to previous row's same metric 
            # (which is daily change in that metric) OR try to find last month's final.
            # Given the prompt format: "+9.2% (+18% vs prev day)", 
            # Let's just return the raw HPRs and let frontend format, 
            # but we need the 'diff' context.
            
            # We will send the full history for the chart anyway used in modals.
            # So here we just send latest numbers.
            pass
            
        stats = {
            'daily_hpr': float(latest['daily_hpr']),
            'monthly_hpr': float(latest['monthly_hpr']),
            'yearly_hpr': float(latest['yearly_hpr']),
            'timestamp': latest['date']
        }
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    """Returns the full history for charts."""
    if not os.path.exists(DATA_FILE):
        return jsonify([])
    
    try:
        df = pd.read_csv(DATA_FILE)
        # Ensure native types for JSON
        data = df.to_dict(orient='records')
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/comparison')
def get_comparison():
    """Returns the comparison table data."""
    try:
        # Use pandas to read the CSV
        df = pd.read_csv('compare.csv')
        # Replace NaN with empty string
        df = df.fillna('')
        # Convert to list of dicts
        data = df.to_dict(orient='records')
        # Get columns for header
        columns = df.columns.tolist()
        return jsonify({'headers': columns, 'rows': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
