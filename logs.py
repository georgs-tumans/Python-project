import json
from datetime import date
import os
import csv
from datetime import datetime

#Class for custom logging needs. 
class MyLogger:

    def __init__(self):
        None
   
    def LogAPICalls(self, API): 
        if API=='YahooFinance':
            callDate = str(date.today().strftime("%m-%Y"))  #only the month  for this API cuz the 500 call monthly limit
        else:
            callDate=str(date.today().strftime("%d.%m.%Y")) #today, cuz gotta keep track of daily call limit
        with open('RequestLog.json', 'r') as fin:
            data=fin.read() 
        obj = json.loads(data)
        if callDate in obj[API]:
            currentCount = obj[API][callDate]
            obj[API][callDate]=currentCount+1
        else:
            obj[API][callDate]=1
        with open('RequestLog.json', 'w') as fout:
            json.dump(obj, fout)

    def LogStockPurchases(self, stock, quantity, purchasePrice, action):
        fName='PurchaseLog.csv'
        with open(r''+fName,'a',  newline='') as fd:
            date = datetime.now()
            date = date.strftime("%d/%m/%Y %H:%M:%S")
            
            fieldnames = ['Time', 'Action','Stock', 'Price']
            writer = csv.DictWriter(fd, fieldnames=fieldnames)
            writer.writerow({'Time': str(date), 'Action': ' '+ action, 'Stock': ' '+str(stock), 'Price': ' '+ str(purchasePrice)})
