import os
import time
import requests
import hmac
import hashlib
import pandas as pd
import numpy as np
import schedule
from datetime import datetime
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
DATA_FILE = 'fund_data.csv'

def get_binance_account_equity():
    """Calculates total account equity from Binance PAPI."""
    base_url = 'https://papi.binance.com'
    endpoint = '/papi/v1/account'
    
    timestamp = int(time.time() * 1000)
    query_string = f'timestamp={timestamp}'
    
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    headers = {'X-MBX-APIKEY': API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Depending on PAPI response structure, 'actualEquity' is usually in the returned object
        # Note: The user mentioned 'actualEnquity' (typo in prompt?), we check for 'actualEquity' or similar.
        # Standard UM Futures uses /fapi/v2/account -> totalWalletBalance / totalMarginBalance
        # Portfolio Marge (PAPI) returns actualEquity.
        
        if 'actualEquity' in data:
            return float(data['actualEquity'])
        else:
            # Fallback for standard structure if PAPI differs or for mock testing if needed
            logging.warning("actualEquity not found in response, checking alternate fields.")
            return float(data.get('totalEquity', 0.0))
            
    except Exception as e:
        logging.error(f"Error fetching Binance data: {e}")
        return None

def initialize_csv():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=[
            'date', 'total_balance', 'principal', 'net_cash_flow', 
            'daily_hpr', 'cumulative_twr', 'monthly_hpr', 'yearly_hpr'
        ])
        df.to_csv(DATA_FILE, index=False)
        logging.info(f"Initialized {DATA_FILE}")

def calculate_stats():
    """
    Main logic to run daily.
    1. Get current Balance (Period End Value for yesterday, technically)
    2. Get Principal (User input or inherited)
    3. Calc Net Cash Flow
    4. Calc HPR & TWR
    """
    logging.info("Starting daily calculation...")
    
    # 1. Get Balance
    # Retry logic handled inside or here? Simple retry here.
    balance = None
    for _ in range(3):
        balance = get_binance_account_equity()
        if balance is not None:
            break
        time.sleep(5)
    
    if balance is None:
        logging.error("Failed to get balance after retries. Aborting calculation.")
        return

    # 2. Load History
    initialize_csv()
    try:
        df = pd.read_csv(DATA_FILE)
    except Exception as e:
        logging.error(f"Error reading CSV: {e}")
        return

    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # Check if entry for today already exists to avoid dupes? 
    # The prompt says run at 00:01 daily. Ideally we append a new row.
    
    # Get Previous Data
    if not df.empty:
        last_row = df.iloc[-1]
        prev_balance = last_row['total_balance'] # Start value for today (approx)
        prev_principal = last_row['principal']
        prev_cumulative_twr_val = last_row['cumulative_twr']
        
        # For precise TWR:
        # HPR = (EndValue / StartValue) - 1.
        # But here StartValue = Prev EndValue + CashFlow.
        # CashFlow logic: Prompt says "Check input". 
        # Since this is a script, we might need to read a separate 'principal.txt' or similar configuration file 
        # because the user can't input interactively at 00:01 in a cron job easily.
        # We will assume a 'current_principal.txt' exists, or we use the last principal if not changed.
        
        current_principal = prev_principal
        if os.path.exists('current_principal.txt'):
            try:
                with open('current_principal.txt', 'r') as f:
                    val = f.read().strip()
                    if val:
                        current_principal = float(val)
            except:
                pass
        
        net_cash_flow = current_principal - prev_principal
        
        # Formula: Each sub-period HPR = (EndCurrent / (EndPrev + CashFlow)) - 1
        # If cashflow timing is unknown, use weight 0.5? Prompt: "Assumption: Cash flow happens at start of sub-period"
        # Prompt says: "Period Start Value = Previous Period End Value + Net Cash Flow"
        
        start_value = prev_balance + net_cash_flow
        
        if start_value == 0:
            daily_hpr = 0
        else:
            daily_hpr = (balance / start_value) - 1
            
        # Cumulative TWR = (1 + PrevTWR) * (1 + DailyHPR) - 1
        # Wait, usually CumTWR is product of (1+r). If stored as 0.1 (10%), then:
        # (1 + 0.1) * (1 + 0.05) - 1 = 1.155 - 1 = 0.155
        new_cumulative_twr = (1 + prev_cumulative_twr_val) * (1 + daily_hpr) - 1
        
    else:
        # First Run
        # Initial Principal?
        current_principal = 0.0
        if os.path.exists('current_principal.txt'):
             with open('current_principal.txt', 'r') as f:
                val = f.read().strip()
                if val:
                    current_principal = float(val)
        
        if current_principal == 0:
            logging.warning("First run with 0 principal. Setting principal = balance for TWR baseline.")
            current_principal = balance
        
        net_cash_flow = current_principal # Initial deposit
        daily_hpr = 0.0
        new_cumulative_twr = 0.0 # Start at 0% return
        
        # Special case for first day calculation if we treat balance as result of day 0?
        # Usually day 0 is just setting baseline.
    
    # Monthly / Yearly HPR
    # Need to filter df for current month/year and compound
    # Since we are appending today's row, we calculate based on new df state + new value?
    # Easier to append first, then calc.
    
    new_row = {
        'date': today_str,
        'total_balance': balance,
        'principal': current_principal,
        'net_cash_flow': net_cash_flow,
        'daily_hpr': daily_hpr,
        'cumulative_twr': new_cumulative_twr,
        'monthly_hpr': 0.0, # Placeholder
        'yearly_hpr': 0.0   # Placeholder
    }
    
    # Append temporarily to calc periods
    # Note: Using concat instead of append
    df_new = pd.DataFrame([new_row])
    df_combined = pd.concat([df, df_new], ignore_index=True)
    
    # Calc Monthly HPR (Current Month)
    current_month = datetime.now().strftime('%Y-%m')
    current_year = datetime.now().strftime('%Y')
    
    # Filter for month
    mask_month = df_combined['date'].astype(str).str.startswith(current_month)
    month_hprs = df_combined.loc[mask_month, 'daily_hpr']
    monthly_hpr_val = np.prod(1 + month_hprs) - 1
    
    # Filter for year
    mask_year = df_combined['date'].astype(str).str.startswith(current_year)
    year_hprs = df_combined.loc[mask_year, 'daily_hpr']
    yearly_hpr_val = np.prod(1 + year_hprs) - 1
    
    # Update values in the new row (which is at the end of df_combined)
    df_combined.at[df_combined.index[-1], 'monthly_hpr'] = monthly_hpr_val
    df_combined.at[df_combined.index[-1], 'yearly_hpr'] = yearly_hpr_val
    
    # Save
    df_combined.to_csv(DATA_FILE, index=False)
    
    logging.info(f"Stats Updated: Daily HPR: {daily_hpr:.2%}, Monthly: {monthly_hpr_val:.2%}, Yearly: {yearly_hpr_val:.2%}")

def run_scheduler():
    logging.info("Scheduler started. Waiting for 00:01...")
    # Schedule everyday at 00:01
    schedule.every().day.at("00:01").do(calculate_stats)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # If run directly without args, maybe run one-off or start scheduler?
    # User asked for script to be generated. I'll make it so it can be imported or run.
    # For demo purposes, we might want to trigger a calc immediately if empty.
    initialize_csv()
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--run-now':
        calculate_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == '--scheduler':
        run_scheduler()
    else:
        print("Usage: python hpr_calculator.py [--run-now | --scheduler]")
