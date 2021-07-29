import pandas as pd
import numpy as np
import requests
import math
import xlsxwriter
from scipy.stats import percentileofscore as score
from statistics import mean

stocks = pd.read_csv('sp_500_stocks.csv')
from secrets import IEX_CLOUD_API_TOKEN

#CREATE VALUE STRATEGY BASED ON P/E RATIO.
#Figure out which API endpoint we need in our url.
symbol = 'AAPL'
api_url = f'https://sandbox.iexapis.com/stable/stock/{symbol}/quote/?token={IEX_CLOUD_API_TOKEN}'
data = requests.get(api_url)
#Status codes tell you whether your http request was successful or not.
#A successful http request will return a status code of 200. Most erroneous requests will return somewhere in 400s.
print(data.status_code)
data = requests.get(api_url).json()
print(data)
#data.json() returns a python dictionary type object.
print(type(data))

price = data['latestPrice']
pe_ratio = data['peRatio']
print([price, pe_ratio])

#EXECUTE A BATCH API CALL

#We define a function chunks to break our n=505 list into n=100 lists.
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    #NOTE: For python loops, looper stops when iterator reaches (or exceeds) end of range.  So for i=end_range, the loop will not execute (it will exit).
    for i in range(0, len(lst), n): #syntax for range is range(first value in range, last value in range, step size).
        yield lst[i:i + n] #yield a string array for each 100 strings in stocks.

#Call chunks function to our case.  Note that function lists can take iterator objects, such as our function chunks.
#symbol_groups is a list of lists.
symbol_groups = list(chunks(stocks['Ticker'], 100))
print(symbol_groups[1])

symbol_strings = []
print(len(symbol_groups)) #returns 6, i.e. number of lists in our list.
#Create 6 entries (len(symbol_groups)) in symbol_strings, each created by comma-separated join.
for i in range(0, len(symbol_groups)):
    symbol_strings.append(','.join(symbol_groups[i]))
    #print(symbol_strings[i])
print(symbol_strings)

my_columns = ['Ticker', 'Price', 'P/E Ratio', 'Number of Shares to Buy']

final_dataframe = pd.DataFrame(columns = my_columns)

for symbol_string in symbol_strings:
    batch_api_call_url = f'https://sandbox.iexapis.com/stable/stock/market/batch?symbols={symbol_string}&types=quote&token={IEX_CLOUD_API_TOKEN}'
    data = requests.get(batch_api_call_url).json()
    for symbol in symbol_string.split(','):
        final_dataframe = final_dataframe.append(
            pd.Series(
                [
                symbol,
                data[symbol]['quote']['latestPrice'],
                data[symbol]['quote']['peRatio'],
                'N/A'
                ],
               index = my_columns),
            ignore_index = True
            )

#REMOVING GLAMOUR STOCKS
#Glamour stock is opposite of Value stock

#Sort dataframe based on P/E ratios
final_dataframe.sort_values('P/E Ratio', ascending = True, inplace = True)
#Remove negative values from the dataframe
final_dataframe = final_dataframe[final_dataframe['P/E Ratio'] > 0]
#Keep top 50 P/E ratios
final_dataframe = final_dataframe[:50]
#Reset index and drop old one
final_dataframe.reset_index(drop = True, inplace = True)
print(final_dataframe)
        
def portfolio_input():
    #Make variable global so we can use it outside the function
    global portfolio_size
    portfolio_size = input('Enter the size of your portfolio: ')
    
    try:
        float(portfolio_size)
        portfolio_size = float(portfolio_size)
    except ValueError:
        print('That is not a number! /nPlease try again.')
        portfolio_size = input('Enter the size of your portfolio: ')
        portfolio_size = float(portfolio_size)

portfolio_input()
position_size = portfolio_size/len(final_dataframe.index)

for row in final_dataframe.index:
    final_dataframe.loc[row, 'Number of Shares to Buy'] = math.floor(position_size/final_dataframe.loc[row, 'Price'])
    
print(final_dataframe)

#BUILD A BETTER AND MORE REALISTIC VALUE STRATEGY: TAKE INTO ACCOUNT MORE THAN ONE METRIC

symbol = 'AAPL'
#Do batch api call for multiple end-points instead of multiple stocks.  The metrics we need are spread out among different end-points.
batch_api_call_url = f'https://sandbox.iexapis.com/stable/stock/market/batch?symbols={symbol}&types=quote,advanced-stats&token={IEX_CLOUD_API_TOKEN}'
data = requests.get(batch_api_call_url).json()

#Price-to-earnings ratio
pe_ratio = data[symbol]['quote']['peRatio']

#Price-to-book ratio
pb_ratio = data[symbol]['advanced-stats']['priceToBook'] 

#Price-to-sales ratio
ps_ratio = data[symbol]['advanced-stats']['priceToSales']

#Following two metrics not given directly by EIX cloud. Instead we need to calculate from constituents.
#Enterprise Value-to-Earnings Before Interest, Taxes, Depreciation, and Amorization ratio
ev = data[symbol]['advanced-stats']['enterpriseValue']
ebitda = data[symbol]['advanced-stats']['EBITDA']
ev_to_ebitda = ev/ebitda

#Enterprice Value-to-Gross Profit ratio
gross_profit = data[symbol]['advanced-stats']['grossProfit']
ev_to_gp = ev/gross_profit

#RV means Robust Value
rv_columns = [
              'Ticker',
              'Price',
              'Number of Shares to Buy',
              'P/E Ratio',
              'PE Percentile',
              'P/B Ratio',
              'PB Percentile',
              'P/S Ratio',
              'PS Percentile',
              'EV/EBITDA Ratio',
              'EV/EBITDA Percentile',
              'EV/GP Ratio',
              'EV/GP Percentile',
              'RV Score'
              ]

rv_dataframe = pd.DataFrame(columns = rv_columns)

for symbol_string in symbol_strings:
    batch_api_call_url = f'https://sandbox.iexapis.com/stable/stock/market/batch?symbols={symbol_string}&types=quote,advanced-stats&token={IEX_CLOUD_API_TOKEN}'
    data = requests.get(batch_api_call_url).json()
    for symbol in symbol_string.split(','):
        ev = data[symbol]['advanced-stats']['enterpriseValue']
        ebitda = data[symbol]['advanced-stats']['EBITDA']
        gross_profit = data[symbol]['advanced-stats']['grossProfit']
        
        #EBITDA is sometimes not given by EIX cloud, e.g. 'None', which makes division impossible. So we add exception for TypeError.
        try:
            ev_to_ebitda = ev/ebitda
        except TypeError:
            #np.NaN returns NaN data structure that is stored in numpy lib.
            ev_to_ebitda = np.NaN
            
        #Gross Profit is sometimes not given by EIX cloud (depends if company provides it or not), e.g. 'None', which makes division impossible. So we add exception for TypeError.
        try:
            ev_to_gp = ev/gross_profit
        except TypeError:
            #np.NaN returns NaN data structure that is stored in numpy lib.
            ev_to_gp = np.NaN
            
        rv_dataframe = rv_dataframe.append(
            pd.Series(
                [
                  symbol,
                  data[symbol]['quote']['latestPrice'],
                  'Number of Shares to Buy',
                  data[symbol]['quote']['peRatio'],
                  'PE Percentile',
                  data[symbol]['advanced-stats']['priceToBook'],
                  'PB Percentile',
                  data[symbol]['advanced-stats']['priceToSales'],
                  'PS Percentile',
                  ev_to_ebitda,
                  'EV/EBITDA Percentile',
                  ev_to_gp,
                  'EV/GP Percentile',
                  'RV Score'
                    ],
                #index = rv_columns specifies which columns of the pandas dataframe (rv_columns) each item of the pandas series should be added/appended to.
                index = rv_columns),
            #ignore_index = True means every row that is added to the pandas dataframe will have its index column value automatically calculated.
            ignore_index = True)

print(rv_dataframe)

#DEAL WITH MISSING DATA IN OUR DATAFRAME

#Dealing with missing data is an important topic in data science.
#There are two main approaches:
#1. Drop missing data from the data set (pandas dropna method is useful here)
#2. Replace missing data with a new value (pandas villna method is useful here)
#In this tutorial we replace missing data with the average non-NaN data point from that column.

#Filtering our rv_dataframe to show any part that isnull() is true.
#axis=1 tells us columns not rows. (axis=0 is rows?)
print(rv_dataframe[rv_dataframe.isnull().any(axis=1)])
#Can print how many rows have missing data
print(rv_dataframe[rv_dataframe.isnull().any(axis=1)].index)

#Loop over relevant columns in rv_dataframe
for column in ['P/E Ratio','P/B Ratio','P/S Ratio','EV/EBITDA Ratio','EV/GP Ratio']:
    #For each null/NaN entry in column, fill it in with the mean of the column values.
    rv_dataframe[column].fillna(rv_dataframe[column].mean(), inplace = True)

#The following should return empty dataframe.
print(rv_dataframe[rv_dataframe.isnull().any(axis=1)])
       
metrics = {
   'P/E Ratio' : 'PE Percentile',
   'P/B Ratio' : 'PB Percentile',
   'P/S Ratio' : 'PS Percentile',
   'EV/EBITDA Ratio' : 'EV/EBITDA Percentile',
   'EV/GP Ratio' : 'EV/GP Percentile'
    }   

for metric in metrics.keys():
    for row in rv_dataframe.index:
        rv_dataframe.loc[row, metrics[metric]] = score(rv_dataframe[metric], rv_dataframe.loc[row, metric])/100
             
print(rv_dataframe)

#Calculating the RV Score

for row in rv_dataframe.index:
    value_percentiles = []
    for metric in metrics.keys():
        value_percentiles.append(rv_dataframe.loc[row, metrics[metric]])
    rv_dataframe.loc[row, 'RV Score'] = mean(value_percentiles)

print(rv_dataframe)

#Note that default for ascending is True so dont really need here.
rv_dataframe.sort_values('RV Score', ascending = True, inplace = True)
rv_dataframe = rv_dataframe[:50]
rv_dataframe.reset_index(drop=True, inplace = True)

print(rv_dataframe)

portfolio_input()

position_size = portfolio_size/len(rv_dataframe.index)

for row in rv_dataframe.index:
    rv_dataframe.loc[row, 'Number of Shares to Buy'] = math.floor(position_size/rv_dataframe.loc[row, 'Price'])

print(rv_dataframe)

#WRITE EXCEL OUTPUT

writer = pd.ExcelWriter('value strategy.xlsx', engine='xlsxwriter')
rv_dataframe.to_excel(writer, 'Value Strategy', index = False)

#Create Formats
background_color = '#0a0a23'
font_color = '#ffffff'

#add_format method takes dictionary as input, defined using curly {} brackets.
string_format = writer.book.add_format(
    {
        'font_color' : font_color,
        'bg_color' : background_color,
        'border' : 1 #1 means to add a solid border around each one.
        }
    )

dollar_format = writer.book.add_format(
    {
        'num_format' : '$0.00',
        'font_color' : font_color,
        'bg_color' : background_color,
        'border' : 1 #1 means to add a solid border around each one.
        }
    )

integer_format = writer.book.add_format(
    {
        'num_format' : '0',
        'font_color' : font_color,
        'bg_color' : background_color,
        'border' : 1 #1 means to add a solid border around each one.
        }
    )

percent_format = writer.book.add_format(
    {
        'num_format' : '0.0%',
        'font_color' : font_color,
        'bg_color' : background_color,
        'border' : 1 #1 means to add a solid border around each one.
        }
    )

float_format = writer.book.add_format(
    {
        'num_format' : '0.0',
        'font_color' : font_color,
        'bg_color' : background_color,
        'border' : 1 #1 means to add a solid border around each one.
        }
    )

column_formats = {
            'A'  : ['Ticker', string_format],
            'B'  : ['Price', dollar_format],
            'C'  : ['Number of Shares to Buy', integer_format],
            'D'  : ['P/E Ratio', float_format],  
            'E'  : ['PE Percentile', percent_format],
            'F'  : ['P/B Ratio', float_format],
            'G'  : ['PB Percentile', percent_format],
            'H'  : ['P/S Ratio', float_format],
            'I'  : ['PS Percentile', percent_format],
            'J'  : ['EV/EBITDA Ratio', float_format],
            'K'  : ['EV/EBITDA Percentile', percent_format],
            'L'  : ['EV/GP Ratio', float_format],
            'M'  : ['EV/GP Percentile', percent_format],
            'N'  : ['RV Score', percent_format]
    }

for column in column_formats.keys():
    writer.sheets['Value Strategy'].set_column(f'{column}:{column}', 25, column_formats[column][1])
    writer.sheets['Value Strategy'].write(f'{column}1', column_formats[column][0], column_formats[column][1])

writer.save()
