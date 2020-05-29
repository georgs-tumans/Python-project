import stockselect as ss
import papertrade as pt
import logs as lg
import requests
import json
import logging as fileLog
import pytz
from datetime import datetime
import time
import yaml
import math
import alpaca_trade_api as tradeapi
import sys

with open("config.yaml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)

trade=pt.PaperTrade()
apiKey=cfg['apiKey']
# purchasingBudget = cfg['purchasingBudget']
# currentMoney = purchasingBudget
purchasingBudget = float(trade.AvailableMoney())
currentMoney = purchasingBudget
dayStartingMoney = purchasingBudget
minRemainder = cfg['minRemainder']
pennyStockLimit = cfg['pennyStockLimit']
selectedStrategy=cfg['strategyToUse']
dailyStocks = None
ownedStocks={}  # dict, symbol:price it was baught for
ownedStocksCount={} #dict, symbol:currently owned count
dailyStocksReselectionCount=0 #because we have strict API call limit

log = lg.MyLogger() 
fileLog.basicConfig(filename='TradeingLog.txt', format='%(asctime)s - %(message)s', level=fileLog.INFO)

#Returns minutes remaining until stock market close
def TradingTimeRemaining():
    marketStatus = trade.GetMarketHours()
    closeTime = str(marketStatus.next_close)
    closeTime = datetime.strptime(closeTime[11:16], '%H:%M')
    currentMarketTime = str(marketStatus.timestamp)
    currentMarketTime = datetime.strptime(currentMarketTime[11:16], '%H:%M')
    difference=closeTime-currentMarketTime
    difference=math.floor(difference.seconds/60)
    return difference

#Sell all stocks at the current market price in order to end day with no stocks left
def SellAll():
    positions = trade.GetPositions()
    if len(positions)>0:
        fileLog.info('Selling all stocks at the end of the day')
        print('Selling all stocks at the end of the day')
        for p in positions:
            trade.SellStock(p.symbol,p.qty,'market', None, None)
            fileLog.info('Selling '+ str(p.symbol) + ' for ~' + str(p.current_price))
            print('Selling '+ str(p.symbol) + ' for ~' + str(p.current_price))
    else:
        fileLog.info('No stocks to sell at the end of the day')
        print('No stocks to sell at the end of the day')


def EndDay():
    trade.CancelAll()
    SellAll()
    currentMoney=float(trade.AvailableMoney())
    finalResult=currentMoney-dayStartingMoney
    fileLog.info("Day finished, day profit/loss: " + str(finalResult))
    print("Day finished, day profit/loss: " + str(finalResult))
    sys.exit()
 
#Purchase all of the selected daily stocks no matter the price 
def InitialPurchase():
    global currentMoney
    fileLog.info('Starting initial stock purchase process')
    print('Starting initial stock purchase process')
    purchasedStockCount=0
    for s in dailyStocks:
        try:
            price=trade.GetStockPrice(s)
            singleStockMaxAmount=(currentMoney-minRemainder)/3
            purchaseCount=math.floor(singleStockMaxAmount/price)
            if purchaseCount==0:
                continue
            date = datetime.now()
            customOrderID=r''+str(date)+'_buy_'+s
            #pielikt pārbaudi, vai šādu skaitu stocks iespējams nopirkt
            trade.BuyStock(s,purchaseCount, "market", customOrderID)
            order=trade.GetOrderInfo(customOrderID)
            orderStatus=order.status
            
            #wait till order gets completely filled
            while orderStatus in ('partially_filled', 'accepted', 'new', 'pending_new', 'accepted_for_bidding' ):
                time.sleep(1)
                order=trade.GetOrderInfo(customOrderID)
                orderStatus=order.status

            if orderStatus=='filled':
                purchasedStockCount+=1
                purchasePrice=float(order.filled_avg_price)
                purchaseCount=float(order.filled_qty)
                currentMoney=currentMoney-(purchasePrice*purchaseCount)
                ownedStocks[s]=purchasePrice
                ownedStocksCount[s]=purchaseCount
                fileLog.info('Bought '+ str(purchaseCount) + ' of '+ str(s) + ' for ' + str(purchasePrice))
                print('Bought '+ str(purchaseCount) + ' of '+ str(s) + ' for ' + str(purchasePrice))
                log.LogStockPurchases(s, purchaseCount, purchasePrice, 'Buy')
            else:
                #skip if the order could not be completed
                fileLog.info('Could not buy: ' + str(s))
                print('Could not buy: ' + str(s))
                continue
        except Exception as e:
            fileLog.error(repr(e))
            print(str(e))
            continue

    return purchasedStockCount

#Sell stocks, when their price is 1% higher than the purchase price
def SellOwnedStocks(tryCount):
    soldStocks=0
    stocksToRemove=[]
    for bs in ownedStocks:
        try:
            currentPrice=trade.GetStockPrice(bs)
            stockPurchasePrice=float(ownedStocks[bs])
            if stockPurchasePrice<200:
                priceToSell=stockPurchasePrice*1.0015
            elif stockPurchasePrice<300:
                priceToSell=stockPurchasePrice*1.001
            else:
                priceToSell=stockPurchasePrice*1.0005

            if tryCount==0:
                print("Trying to sell " + str(bs) + " for " + str(priceToSell))
                fileLog.info('Sold '+ str(bs) + 'of '+ str(bs) + ' for ' + str(currentPrice))

            if currentPrice>priceToSell:
                date = datetime.now()
                customOrderID=r''+str(date)+'_sell_'+bs
                trade.SellStock(bs,ownedStocksCount[bs],'limit', customOrderID, currentPrice)
                order=trade.GetOrderInfo(customOrderID)
                orderStatus=order.status
                while orderStatus in ('partially_filled', 'accepted', 'new', 'pending_new', 'accepted_for_bidding'):
                    time.sleep(1)
                    order=trade.GetOrderInfo(customOrderID)
                    orderStatus=order.status 
                
                if orderStatus=='filled':
                    soldStocks+=1
                    stocksToRemove.append(bs)
                    fileLog.info('Sold '+ str(ownedStocksCount[bs]) + ' of '+ str(bs) + ' for ' + str(currentPrice))
                    print('Sold '+ str(ownedStocksCount[bs]) + ' of '+ str(bs) + ' for ' + str(currentPrice))
                    log.LogStockPurchases(bs, ownedStocksCount[bs], currentPrice, 'Sell')
                
                else:           #failed to sell stocks
                    fileLog.info('Could not sell: ' + str(bs))
                    print('Could not sell: ' + str(bs))
                    continue
        except Exception as e:
            fileLog.error(repr(e))
            print(str(e))
            continue

    for r in stocksToRemove:
        del ownedStocks[r]
        del ownedStocksCount[r]
    return soldStocks

#Initially buys the 3 selected stocks for the market price
#Works until all stocks are sold
#Repeats until market closes in 10 (2) minutes
#To do - implement smarter purchases based on some indicators
def BasicStrategy():
    global currentMoney
    # singleStockMaxAmount=(currentMoney-minRemainder)/3
    # if singleStockMaxAmount<=pennyStockLimit:
    #     SellOwnedStocks()
    #     BasicStrategy()
    purchasedStockCount=InitialPurchase()
    counter=0
    #limited number of tries to buy right after starting the script
    while purchasedStockCount==0 and counter<100:
        purchasedStockCount=InitialPurchase()
        time.sleep(1)
        counter+=1
    if purchasedStockCount==0:      #after 100 unsuccesful tries, start from beginning by reevaluating daily stocks (if >10 min remaining until market closure)
        fileLog.info('Couldnt buy single stock after 100 tries, reselecting daily stocks and starting anew')
        print('Couldnt buy single stock after 100 tries, reselecting daily stocks and starting anew')
        trade.CancelAll()
        if TradingTimeRemaining()>10 and dailyStocksReselectionCount<=5:  
            currentMoney=float(trade.AvailableMoney())
            stockSelectionService = ss.SelectedStocks(purchasingBudget, currentMoney, minRemainder, pennyStockLimit)
            stockSelectionService.GetTopGainers(0, False) 
            dailyStocks=stockSelectionService.selectedStocks
            dailyStocksReselectionCount+=1
            fileLog.info('Re-selected daily stocks: ' + str(dailyStocks))
            print('Re-selected daily stocks: ' + str(dailyStocks))
            BasicStrategy()
        else:
             EndDay()
    else:                   #If we managed to buy some stocks
        currentMoney=float(trade.AvailableMoney())
        fileLog.info('Remaining money: ' + str(currentMoney))
        print('Remaining money: ' + str(currentMoney))
        if TradingTimeRemaining()>10:
            soldStocksCount=0
            sellTryCount=0
            while soldStocksCount!=purchasedStockCount:
                soldStocksCount=SellOwnedStocks(sellTryCount)
                sellTryCount+=1
                if TradingTimeRemaining()<2:
                    EndDay()
            BasicStrategy()
        else:
            EndDay()

#Checks whether the selected stocks are all tradeaboe through Alpaca API   
def CheckStockAvailability():
    global dailyStocks
    for s in dailyStocks:
        if not trade.IsTradeable(s):
            fileLog.info('The selected daily stock ' + str(s) + ' is not tradeable')
            print('The selected daily stock ' + str(s) + ' is not tradeable')
            return False
    
    return True
    

fileLog.info('Starting the script')
print('Starting the script')
fileLog.info('Currently available money: ' + str(dayStartingMoney))
print('Current available money: ' + str(dayStartingMoney))
# #Check the market status every minute 
marketStatus=trade.MarketStatus()
while not marketStatus:
    print("Market closed")
    time.sleep(60)
    marketStatus=trade.MarketStatus()
fileLog.info('Market open')
print("Market open")

# loop until we can make a selection
selectionMade=False
while not selectionMade:
    try:
        stockSelectionService = ss.SelectedStocks(purchasingBudget, currentMoney, minRemainder, pennyStockLimit)
        if selectedStrategy==0: #Basic strategy
            stockSelectionService.GetTopGainers(0, False) 
        else:
            stockSelectionService.GetTopActives(0, False) 
        dailyStocks=stockSelectionService.selectedStocks
        Tradeble=CheckStockAvailability()
        while not Tradeble:
            stockSelectionService.GetTopGainers(0, False) 
            dailyStocks=stockSelectionService.selectedStocks
            Tradeble=CheckStockAvailability()
        selectionMade=True

    except Exception as e:
        fileLog.error('Failed to select stocks: ', repr(e))
        print('Failed to select stocks: ', repr(e))
fileLog.info('The selected stocks: '+ str(dailyStocks))
print("The selected stocks: "+str(dailyStocks))
# dailyStocks={'ARGX': 214.87, 'ADS': 49.635, 'NVAX': 52.32} #only for development so not to waste api calls

# Strategy selection from the config
if selectedStrategy==0:
    BasicStrategy()
    # SellAll()
    # EndDay()

    
   
    



################Testing area##################################################
# price=GetStockPrice('FTSV', '5', apiKey)
# trade.AccountStatus()
# print(currentMoney)

# selectedStocks = ss.SelectedStocks(purchasingBudget, currentMoney, minRemainder, pennyStockLimit)
# selectedStocks.GetTopGainers(0, False)
# currentMoney=selectedStocks.currentMoney
# dailyStocks=selectedStocks.selectedStocks
# fileLog.info('The selected stocks: '+ str(dailyStocks))
# print("The selected stocks: "+str(dailyStocks))
# print("Remaining money: " + str(currentMoney))
# for stock in dailyStocks:
#     if trade.IsTradeable(stock):
        # trade.BuyAtMarketPrice(stock,1)
        #trade.SellAtMarketPrice(stock,1)
