import sys
sys.path.append('/home/ubuntu/main_bot/utilities')
from custom_indicators import CustomIndicators as ci
from spot_ftx import SpotFtx
import pandas as pd
import ta
import ccxt
from datetime import datetime
import time
import discord
import os
import json
from math import *
from pickle import *

now = datetime.now()
print(now.strftime("%d-%m %H:%M:%S"))

ftx = SpotFtx(
        apiKey='',
        secret='',
        subAccountName=''
    )

pairList = [
    'BTC/USD',
    'ETH/USD',
    'BNB/USD',
    'LTC/USD',
    'DOGE/USD',
    'SOL/USD',
    'AVAX/USD',
    'SHIB/USD',
    'LINK/USD',
    'UNI/USD',
    'MATIC/USD',
    'AXS/USD',
    'CRO/USD',
    'TRX/USD',
    'FTM/USD',
    'MANA/USD',
    'SAND/USD'
]

timeframe = '1h'

# -- Variables d'indicateurs --
# Awesome Oscillator
aoParam1 = 6
aoParam2 = 22
# Stochastic RSI
stochWindow = 14
# William R
willWindow = 14
# TRIX
trixWindow = 9
trixSignal = 21
# MACD
fast = 12
slow = 26
signal = 9

# -- Hyper parameters --
maxOpenPosition = 2
stochOverBought = 0.8
stochOverSold = 0.2
willOverSold = -85
willOverBought = -10
TpPct = 0.1
messages = ""

CUR_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(CUR_DIR, "data.json")

dfList = {}
for pair in pairList:
    # print(pair)
    df = ftx.get_last_historical(pair, timeframe, 210)
    dfList[pair.replace('/USD','')] = df

for coin in dfList:
    # -- Drop all columns we do not need --
    dfList[coin].drop(columns=dfList[coin].columns.difference(['open','high','low','close','volume']), inplace=True)

    # -- Indicators, you can edit every value --
    dfList[coin]['AO']= ta.momentum.awesome_oscillator(dfList[coin]['high'],dfList[coin]['low'],window1=aoParam1,window2=aoParam2)
    dfList[coin]['STOCH_RSI'] = ta.momentum.stochrsi(close=dfList[coin]['close'], window=stochWindow)
    dfList[coin]['WillR'] = ta.momentum.williams_r(high=dfList[coin]['high'], low=dfList[coin]['low'], close=dfList[coin]['close'], lbp=willWindow)
    dfList[coin]['EMA100'] =ta.trend.ema_indicator(close=dfList[coin]['close'], window=100)
    dfList[coin]['EMA200'] =ta.trend.ema_indicator(close=dfList[coin]['close'], window=200)

    trix = ci.trix(close=dfList[coin]['close'],trixLength=trixWindow, trixSignal=trixSignal)
    dfList[coin]['TRIX_HISTO'] = trix.trix_histo()

    MACD = ta.trend.MACD(close=dfList[coin]['close'], window_fast=fast, window_slow=slow, window_sign=signal)
    dfList[coin]['MACD'] = MACD.macd()
    dfList[coin]['MACD_SIGNAL'] = MACD.macd_signal()
    dfList[coin]['MACD_DIFF'] = MACD.macd_diff()

print("Data and Indicators loaded 100%")

# -- Condition to BUY market --
def buyCondition(row, previousRow=None):
    if (
        row['AO'] >= 0
        and previousRow['AO'] > row['AO']
        and row['WillR'] < willOverSold
        and row['EMA100'] > row['EMA200']
    ):
        return True
    else:
        return False

def buyConditionTrix(row, previousRow):
    if(
        row['TRIX_HISTO'] > 0
        and row['STOCH_RSI'] < stochOverBought
        and row['EMA100'] > row['EMA200']
        and row['MACD'] > 0
    ):
        return True
    else:
        return False

# -- Condition to SELL market --
def sellCondition(row, previousRow=None):
    if (
        (row['AO'] < 0
        and row['STOCH_RSI'] > stochOverSold)
        or row['WillR'] > willOverBought
    ):
        return True
    else:
        return False

def sellConditionTrix(row, previousRow):
    if (
        row['TRIX_HISTO'] < 0
        and row['STOCH_RSI'] > stochOverSold
        and row['MACD_DIFF'] < previousRow['MACD_DIFF']
    ):
        return True
    else:
        return False

# -- Check balance and DATA -- 
coinBalance = ftx.get_all_balance()
coinInUsd = ftx.get_all_balance_in_usd()
usdBalance = coinBalance['USD']
del coinBalance['USD']
del coinInUsd['USD']
totalBalanceInUsd = usdBalance + sum(coinInUsd.values())
coinPositionList = []
for coin in coinInUsd:
    if coinInUsd[coin] > 0.05 * totalBalanceInUsd:
        coinPositionList.append(coin)
openPositions = len(coinPositionList)

if os.path.exists(DATA_PATH):
    with open(DATA_PATH, "r") as f:
        DATA = json.load(f)

else:
    DATA = []

#Sell
for coin in coinPositionList:
        if (sellCondition(dfList[coin].iloc[-2], dfList[coin].iloc[-3]) == True
            or sellConditionTrix(dfList[coin].iloc[-2], dfList[coin].iloc[-3]) == True):
            openPositions -= 1
            symbol = coin+"/USD"
            cancel = ftx.cancel_all_open_order(symbol)
            time.sleep(1)
            actualPrice = float(ftx.convert_price_to_precision(symbol, ftx.get_bid_ask_price(symbol)['ask'])) 
            sell = ftx.place_market_order(symbol,'sell',coinBalance[coin])
            print(cancel)
            print("Sell", coinBalance[coin], coin, sell)

            if symbol in DATA:
                index = DATA.index(symbol)
                price = DATA(index + 1)

                profit = ((actualPrice - price)/price) * 100

                DATA.remove(index)
                DATA.remove(index + 1)

            if profit > 0:
                messages = "Sell " + str(coin) + " at " + str(actualPrice) + "$. " + " --> " + " +" + str(profit) + "%"

            else :
                messages = "Sell " + str(coin) + " at " + str(actualPrice) + "$. " + " --> " + str(profit) + "%"

            if messages != "":
                    TOKEN = ""
                    client = discord.Client()
                    @client.event
                    async def on_ready():
                        print(f'{client.user} has connected to Discord!')


                        channel = client.get_channel()
                        await channel.send(messages)

                        await client.close()
                        time.sleep(1)

                    client.run(TOKEN)

        else:
            print("Keep",coin)

#Buy
if openPositions < maxOpenPosition:
    for coin in dfList:
        if coin not in coinPositionList:
            if (buyCondition(dfList[coin].iloc[-2], dfList[coin].iloc[-3]) == True 
                or buyConditionTrix(dfList[coin].iloc[-2], dfList[coin].iloc[-3]) == True
                and openPositions < maxOpenPosition):
                
                time.sleep(1)
                usdBalance = ftx.get_balance_of_one_coin('USD')
                symbol = coin+'/USD'

                buyPrice = float(ftx.convert_price_to_precision(symbol, ftx.get_bid_ask_price(symbol)['ask'])) 
                tpPrice = float(ftx.convert_price_to_precision(symbol, buyPrice + TpPct * buyPrice))
                buyQuantityInUsd = usdBalance * 1/(maxOpenPosition-openPositions)

                if openPositions == maxOpenPosition - 1:
                    buyQuantityInUsd = 0.95 * buyQuantityInUsd

                buyAmount = ftx.convert_amount_to_precision(symbol, buyQuantityInUsd/buyPrice)

                buy = ftx.place_market_order(symbol,'buy',buyAmount)
                time.sleep(2)
                tp = ftx.place_limit_order(symbol,'sell',buyAmount,tpPrice)
                try:
                    tp["id"]
                except:
                    time.sleep(2)
                    tp = ftx.place_limit_order(symbol,'sell',buyAmount,tpPrice)
                    pass
                
                DATA.append(symbol)
                DATA.append(buyPrice)

                messages = "Buy " + str(coin) + " at " + str(buyPrice) + "$"

                if messages != "":
                    TOKEN = ""
                    client = discord.Client()
                    @client.event
                    async def on_ready():
                        print(f'{client.user} has connected to Discord!')

                        channel = client.get_channel()
                        await channel.send(messages)

                        await client.close()
                        time.sleep(1)

                    client.run(TOKEN)

                print("Buy",buyAmount,coin,'at',buyPrice,buy)
                print("Place",buyAmount,coin,"TP at",tpPrice, tp)

                openPositions += 1
                
                # Write new position in json file
                with open(DATA_PATH, "w") as f:
                    json.dump(DATA, f, indent=4)