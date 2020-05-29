# Class/module for initial 3 stock selection that will be used for trading on any given day
import requests
import logs as lg
import logging as fileLog
import papertrade as pt
import yaml

class SelectedStocks:

    def __init__(self, budget, money, minRemainder, pennyStockLimit):
        self.stockBudget = budget
        self.currentMoney = money
        self.selectedStocks={}
        self.allStocks={}
        self.stocksEvaluated = 0
        self.minRemainder = minRemainder
        self.pennyStockLimit = pennyStockLimit
        self.log = lg.MyLogger()
        fileLog.basicConfig(filename='TradeingLog.txt', format='%(asctime)s - %(message)s', level=fileLog.INFO)
        with open("config.yaml", 'r') as ymlfile:
            self.cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
        self.trade=pt.PaperTrade()
        self.selectedStrategy = self.cfg["strategyToUse"]

    #Get 6 top-movers (top gainers) at the given moment from Yahoo Finance
    def GetTopGainers (self, offset, fromMoreMoney):
        stocklist=[]
        url = "https://apidojo-yahoo-finance-v1.p.rapidapi.com/market/get-movers"
        querystring = {"region":"US","lang":"en","start":offset}
        headers = {
        'x-rapidapi-host': self.cfg["rapidAPIEndpoint"],
        'x-rapidapi-key': self.cfg["rapidAPIKey"]
        }
        try:
              response = requests.request("GET", url, headers=headers, params=querystring).json()
        except Exception as e:
            print("Exception occured while getting and deserializing initial stock list from YahooFinance: "+ repr(e))
            fileLog.error('Error while calling YahooFinance from GetTopGainers() and deserializing data: %s', repr(e))
            self.log.LogAPICalls('YahooFinance')
            raise
        else:
            self.log.LogAPICalls('YahooFinance')
            if response["finance"]["error"]==None:
                stocks = response["finance"]["result"][0].get("quotes")
                for s in stocks:
                    stocklist.append(s["symbol"])
                self.GetStockData(stocklist, fromMoreMoney)
            else:
                print('Failed to retreive data from Yahoo - ' + str(response["finance"]["error"]))
                fileLog.error('YahooFinance called from GetTopGainers() returned error: %s', str(response["finance"]["error"]))
                self.GetTopGainers(offset, fromMoreMoney) #try again in case of an error

    #Get 6 top-movers (top actives - both gainers and losers) at the given moment from Yahoo Finance
    def GetTopActives (self, offset, fromMoreMoney):
        stocklist=[]
        url = "https://apidojo-yahoo-finance-v1.p.rapidapi.com/market/get-movers"
        querystring = {"region":"US","lang":"en","start":offset}
        headers = {
        'x-rapidapi-host': self.cfg["rapidAPIEndpoint"],
        'x-rapidapi-key': self.cfg["rapidAPIKey"]
        }
        try:
            response = requests.request("GET", url, headers=headers, params=querystring).json()
        except Exception as e:
            print("Exception occured while getting and deserializing initial stock list from YahooFinance: "+ repr(e))
            fileLog.error('Error while calling YahooFinance from GetTopActives() and deserializing data: %s', repr(e))
            self.log.LogAPICalls('YahooFinance')
            raise
        else:
            self.log.LogAPICalls('YahooFinance')
            if response["finance"]["error"]==None:
                stocks = response["finance"]["result"][2].get("quotes")
                for s in stocks:
                    stocklist.append(s["symbol"])
                self.GetStockData(stocklist, fromMoreMoney)
            else:
                print('Failed to retreive data from Yahoo - ' + str(response["finance"]["error"]))
                fileLog.error('YahooFinance called from GetTopActives() returned error: %s', str(response["finance"]["error"]))
                self.GetTopActives(offset, fromMoreMoney) #try again in case of an error


    #Gets the previously 6 selected stock info, so we can start selecting the ones to track throughout the day
    def GetStockData(self, stocks, fromMoreMoney):
        stockPrices={}
        try:
            for s in stocks:
                if self.trade.IsTradeable(s):
                    price=float(self.trade.GetStockPrice(s))
                    stockPrices[s]=price
                    if s not in self.allStocks:
                        self.allStocks[s]=price
                else:
                    continue
            if not fromMoreMoney:
                self.SelectStocks(stockPrices)
            else:
                self.stocksEvaluated = self.stocksEvaluated+6
        except Exception as e:
            print('Failed get stock data - ' + str(e))
            fileLog.error('Failed get stock data - ' + repr(e))
            raise


    #Makes the selection of 3 stocks, that will be tracked throughout the day
    def SelectStocks (self, stocks):
        self.stocksEvaluated = self.stocksEvaluated+6
        #print("Incoming stocks: " + str(stocks))
        for s in stocks:
            #no point to continue if we have the selection of 3 stocks already:
            if (len(self.selectedStocks)>=3):
                break
            #we dont want to count the same stock twice
            if (s in self.selectedStocks):
                continue
            price=stocks[s]
            #selection by the price criteria: less than half of the whole budget, more than the pennystock limit and less than remaining money-untouchable remainder
            if (price>=self.pennyStockLimit and price<=(self.stockBudget/2) and price<=(self.currentMoney-self.minRemainder)):
                self.currentMoney=self.currentMoney-price
                self.selectedStocks[s]=stocks[s]
        
        #If we have less than 3 stocks after the selection process, go back to getting the next 6 top movers from Yahoo
        if (len(self.selectedStocks)<3):
            if self.selectedStrategy==0:
                self.GetTopGainers(self.stocksEvaluated, False)   
            else:
                self.GetTopActives(self.stocksEvaluated, False)   
        # If we have the selection, but have considerable amount of money left, replace the cheapest stock with smth more expesive    
        elif ((self.currentMoney)>=self.stockBudget/2.5):
            print ("Starting the selected stock replacement process..")
            print ("Originally selected stocks: "+ str(self.selectedStocks)) #for testing the selection before adjustments
            fileLog.info('Replacing stocks.. Original selection: %s', self.selectedStocks)
            loopCount=1
            while ((self.currentMoney)>=self.stockBudget/2.5):
                print("Iteration " + str(loopCount))
                fileLog.info('Replacement iteration: %s', loopCount)
                self.SpendMoreMoney()
                loopCount=loopCount+1
                print("Currently selected stocks: " + str(self.selectedStocks))
                fileLog.info("Currently selected stocks: " + str(self.selectedStocks))
                if(loopCount>3):
                    fileLog.info('More than 7 iteration, stopping the stock replacement process')
                    print ("Finished the stock replacement process!")
                    break                       #need exit condition in case no stocks satisfy the replacement criteria
            fileLog.info('Stock selection after replacement: %s', self.selectedStocks)
        
        


    def SpendMoreMoney(self):
        #cheapestSelectedStockPrice - cheapest stock price (dict value)
        #cheapestSelectedStock - cheapest stock symbol (dict key)

        #finding the cheapest stock currently selected:
        cheapestSelectedStock=list(self.selectedStocks.keys())[0]
        for s in self.selectedStocks:
            if(self.selectedStocks[s]<self.selectedStocks[cheapestSelectedStock]):
                cheapestSelectedStock=s
        print("Cheapest stock: " + str(cheapestSelectedStock))
        fileLog.info('Stock to be replaced: %s', cheapestSelectedStock)
        cheapestSelectedStockPrice = self.selectedStocks[cheapestSelectedStock]

        #collecting more info for price replacement
        if self.selectedStrategy==0:
                self.GetTopGainers(self.stocksEvaluated, True)   
        else:
            self.GetTopActives(self.stocksEvaluated, True)  

        print("All stocks: " + str(self.allStocks))
        fileLog.info("All stocks: " + str(self.allStocks))
        #switching the cheapest stock for the first more expensive one
        for a in self.allStocks:
            if (a in self.selectedStocks):
                continue
            currentStockPrice=self.allStocks[a]
            if (currentStockPrice>cheapestSelectedStockPrice and currentStockPrice<((self.currentMoney-self.minRemainder)+cheapestSelectedStockPrice)):
                self.selectedStocks[a]=currentStockPrice
                self.selectedStocks.pop(cheapestSelectedStock)
                self.currentMoney=(self.currentMoney+cheapestSelectedStockPrice)-currentStockPrice
                print("Replaced " + cheapestSelectedStock + " with " + str(a))
                fileLog.info("Replaced " + cheapestSelectedStock + " with " + str(a))
                break

    

        