# -*- coding: utf-8 -*-
"""
Created on Fri Mar  8 19:30:24 2019

@author: nicholaserikdann
"""

####################################
#            LIBRARIES
####################################

import pandas as pd
import numpy as np
import pandas_datareader.data as web
import fix_yahoo_finance as fix
import datetime as dt
import sys
import re
import time
import requests
from bs4 import BeautifulSoup
import random
from matplotlib import pyplot as plt

####################################
#        FUNCTIONS / CLASSES        
####################################

### Main Functions ###

def scrape_wiki (url):
    """Scrapes wikipedia url and returns a list of tickers (symbols) for index components"""
    website_url = requests.get(url).text
    soup = BeautifulSoup (website_url,'lxml')
    table = soup.find('table', {'class' : 'wikitable sortable'})
    links = table.findAll('a')
    # obtain references from links
    links_2 = []    
    for l in links:
        links_2.append(l.get('href'))
    
    # split links
    split_links = []
    for l in links_2:
        split_links.append(l.split ("/"))
    
    # identify and group symbols in a list of tickers
    tickers = []
    for sl in split_links:
        try:    
            if sl[0] != '':
                if sl[2] == 'www.nyse.com' or sl[2] == 'www.nasdaq.com':
                    split = sl[4].split(":")
                    if len(split) > 1:
                        tickers.append(split[1])
                    else:
                        tickers.append(split[0].upper())
                else:
                    pass
            else:
                pass
        except IndexError:
            pass
    return tickers

def get_data(ticker):
    """Creates Dataframe with market data for the provided ticker
    ---------------------------------------------------------------------------
    inputs:
        ticker: str type representing the security's symbol in the market
    outputs:
        df structure with relevant market data (open, close, high, low, volume) 
        for sessions encompassed between start and end date
    ---------------------------------------------------------------------------
    """
    start = dt.datetime (1989,2,1)
    end = dt.datetime (2019,2,1)
    data = web.DataReader (ticker,'yahoo', start, end)
    a_close = data['Adj Close']
    return a_close


def portfolio_generator(df,k=10, n=10):
    # generate random portfolios
    portfolio_dict={}
    portfolio_dict['portfolio_0']=df[index]
    for i in range(1,k+1):
        portfolio_dict['portfolio_{0}'.format(i)]=df[random.sample(tickers,n)]
    return portfolio_dict

def delta_calculator(df,n=10):
    df=np.log(df)-np.log(df).shift(n)
    df=df.dropna()
    return df

def scenario_identificator(df, window=500):
    df_2=pd.DataFrame(index=df.index, columns=df.columns)  
    progress=progress_bar(len(df),fmt=progress_bar.full)
    print()
    print('Calculating historic protfolio average returns for each window')
    for i in range(len(df)):
        if i-window>=0:
            df_2.loc[df_2.index[i]]=df[i-window:i].mean()
        else:
            pass
        progress.current+=1
        progress()
        time.sleep(0.1)
    progress.done()
    df_2=df_2.dropna()
    mean=df_2.mean()
    pos_th=mean+df_2.std()
    neg_th=mean-df_2.std()
    boom_th=mean+df_2.std()*2
    stress_th=mean-df_2.std()*2
    return scenario_labeler(df_2,boom_th,pos_th,neg_th,stress_th)

def var_calculator(df, window=500): 
    var_df=pd.DataFrame(index=df.index[window:])
    progress=progress_bar(len(df.columns),fmt=progress_bar.full)
    print()
    print('Calculating historic VaR values for each portfolio')
    for col in df.columns:
        df_2=df[col]
        var_vector=[]
        for i in range(len(df_2)):
            if i-window>=0:
                var_vector.append(df_2[i-window:i].sort_values(ascending=False)[round(len(df_2[i-window:i])*0.99)])
            else:
                pass
        var_df[col]=var_vector
        progress.current+=1
        progress()
        time.sleep(0.1)
    progress.done()
    return var_df

def es_calculator(df,window=500):
    es_df=pd.DataFrame(index=df.index[window:])
    progress=progress_bar(len(df.columns),fmt=progress_bar.full)
    print()
    print('Caluclating historic ES values for each portfolio')
    for col in df.columns:
        df_2=df[col]
        es_vector=[]
        for i in range(len(df_2)):
            if i-window>=0:
                es_vector.append(df_2[i-window:i].sort_values(ascending=False)[round(len(df_2[i-window:i])*0.99)+1:].mean())
            else:
                pass
        es_df[col]=es_vector
        progress.current+=1
        progress()
        time.sleep(0.1)
    progress.done()
    return es_df

def backtester(scenario_matrix, PL_matrix, VaR_matrix, ES_matrix):
    idx=scenario_matrix.index
    lvl_1=scenario_matrix.columns
    cube=pd.DataFrame(index=idx,columns=pd.MultiIndex.from_product([lvl_1,['Scenario','P&L','VaR','ES', 'VaR - Back-test', 'ES - Back-test']]))
    for portfolio in lvl_1:
        table=pd.DataFrame()
        table['Scenario']=scenario_matrix[portfolio]
        table['P&L']=PL_matrix.loc[table.index,portfolio]
        table['VaR']=VaR_matrix[portfolio]
        table['ES']=ES_matrix[portfolio]
        table['VaR - Back-test']=table['VaR']<table['P&L']
        table['ES - Back-test']=table['ES']<table['P&L']
        cube[portfolio]=table
    return cube

def results_summary(cube):
    matrix=pd.DataFrame(index=['% KOs - VaR', '% KOs - ES','Max Period KO - VaR', 'Max Period KO - ES', 'Max Excess Loss - VaR', 'Max Excess Loss - ES'], 
                           columns=pd.MultiIndex.from_product([cube.columns.levels[0],['Boom', 'Positive', 'Neutral', 'Negative', 'Stressed']]))
    progress=progress_bar(len(cube.columns.levels[0]),fmt=progress_bar.full)
    print()
    print('Summarizing back-test results for each portfolio')
    for p in cube.columns.levels[0]:
        table=pd.DataFrame(index=['% KOs - VaR', '% KOs - ES', 'Max Period KO - VaR', 'Max Period KO - ES', 'Max Excess Loss - VaR', 'Max Excess Loss - ES'], 
                           columns=['Boom', 'Positive', 'Neutral', 'Negative', 'Stressed'])
        ko_periods=cube[p].drop(['P&L','VaR','ES'],axis=1)
        ko_periods['VaR - Back-test']=max_ko_period_calculator(ko_periods['VaR - Back-test'])
        ko_periods['ES - Back-test']=max_ko_period_calculator(ko_periods['ES - Back-test'])
        ko_periods=ko_periods.groupby('Scenario').max()
        for col in table.columns:
            var_report=cube[p].where(cube[p,'VaR - Back-test']==False).dropna().where(cube[p,'Scenario']==col).dropna()
            es_report=cube[p].where(cube[p,'ES - Back-test']==False).dropna().where(cube[p,'Scenario']==col).dropna()
            table.loc['% KOs - VaR',col]=var_report.count().max()/len(cube[p])*100
            table.loc['% KOs - ES',col]=es_report.count().max()/len(cube[p])*100
            table.loc['Max Excess Loss - VaR',col]=(var_report['P&L']-var_report['VaR']).min()
            table.loc['Max Excess Loss - ES',col]=(es_report['P&L']-es_report['ES']).min()
            if col in ko_periods.index:
                table.loc['Max Period KO - VaR',col]=ko_periods.loc[col,'VaR - Back-test']
                table.loc['Max Period KO - ES',col]=ko_periods.loc[col,'ES - Back-test']
            else:
                pass
        matrix[p]=table
        progress.current+=1
        progress()
        time.sleep(0.1)
    progress.done()
    return matrix

### Support Functions ###

def scenario_labeler(df, boom_thresholds, pos_thresholds, neg_thresholds, stress_thresholds):
    progress=progress_bar(len(df.columns),fmt=progress_bar.full)
    print()
    print ('Classifying historic scenarios for each portfolio')    
    labels=pd.DataFrame(index=df.index, columns=df.columns)
    for p in labels.columns:
        boom=boom_thresholds[p]
        pos=pos_thresholds[p]
        neg=neg_thresholds[p]
        strs=stress_thresholds[p]
        for i in labels.index:
            val=df.loc[i,p]
            if val>=boom:
                labels.loc[i,p]='Boom'
            elif val>=pos:
                labels.loc[i,p]='Positive'
            elif val<=strs:
                labels.loc[i,p]='Stressed'
            elif val<=neg:
                labels.loc[i,p]='Negative'
            else:
                labels.loc[i,p]='Neutral'
        progress.current+=1
        progress()
        time.sleep(0.1)
    progress.done()
    return labels

def max_ko_period_calculator(series):
    series=series.tolist()
    val=0
    vector=[]
    for i in series:
        if i==False:
            val+=1
        else:
            val=0
        vector.append(val)
    return vector

### Classess ###

class progress_bar(object):
    default='Progress: %(bar)s %(percent)3d%%'
    full='%(bar)s %(current)d/%(total)d (%(percent)3d%%) %(remaining)d to go'
    
    def __init__(self, total, width=40, fmt=default, symbol='=', output=sys.stderr):
        assert len(symbol)==1
        
        self.total=total
        self.width=width
        self.symbol=symbol
        self.output=output
        self.fmt=re.sub(r'(?P<name>%\(.+?\))d', r'\g<name>%dd' % len(str(total)), fmt)
        self.current=0
        
    def __call__(self):
        percent=self.current/float(self.total)
        size=int(self.width*percent)
        remaining=self.total-self.current
        bar='['+self.symbol*size+' '*(self.width - size)+']'
        
        args={'total':self.total,
              'bar':bar,
              'current':self.current,
              'percent':percent*100,
              'remaining': remaining
              }
        print( '\r'+self.fmt%args, file=self.output, end='')
    
    def done(self):
        self.current=self.total
        self()
        print('', file=self.output)
        
####################################
#             MAIN CODE
####################################

if __name__ == "__main__":
    
    print('Volatility and Risk - Value-at-Risk (VaR) vs Expected Shortfall (ES)')
    print()
    
    # scrape wikipedia for tickers
    url='https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
    tickers=scrape_wiki(url)
    
    # yahoo finance override
    fix.pdr_override ()
    
    # define index and get market data
    index='^DJI' # Dow Jones Idustrial Average Index
    loaded_tickers=[]
    data=pd.DataFrame(columns=[index]+tickers)
    progress=progress_bar(len(data.columns),fmt=progress_bar.full)
    print('Loading Market Data')
    while len(data.columns)>len(loaded_tickers):
        for col in data.columns:
            if col not in loaded_tickers:
                try:
                    data[col]=get_data(col)
                    loaded_tickers.append(col)
                    progress.current+=1
                    progress()
                    time.sleep(0.1)
                except Exception as e:
                    pass
    progress.done()
    
    # series reconstruction
    data.fillna(method='bfill', axis=1, inplace=True)

    # generate random portfolios
    portfolios=portfolio_generator(data)
        
    # calculate historic P&L vectors for each portfolio
    hist_pl=pd.DataFrame(columns=portfolios.keys())
    for p in portfolios.keys():
        if p != 'portfolio_0':
            hist_pl[p]=delta_calculator(portfolios[p]).mean(axis=1)
        else:
            hist_pl[p]=delta_calculator(portfolios[p])
    
    # identify scenarios
    scenarios=scenario_identificator(hist_pl)
    
    # implement VaR for each portfolio
    var=var_calculator(hist_pl)
    
    # implement ES for each portfolio
    es=es_calculator(hist_pl)
    
    # back-test strategies
    metrics=backtester(scenarios, hist_pl, var, es)
    
    # summarize results
    summary=results_summary(metrics)
    print()
    print('Summarized results of VaR and ES back-testing:')
    for p in summary.columns.levels[0]:
        print()
        print(p)
        print(summary[p])

    for i in summary.index:
        plt.figure()
        for p in summary.columns.levels[0]:
            summary.loc[i,p].plot(label=p)
        plt.title(i)
        plt.legend()
        plt.show()
    