import os
import sys
import pickle
import pandas as pd
from tqdm.auto import tqdm
from datetime import datetime

from PyQt5 import QtCore

# Exception Error Handling
import warnings
warnings.filterwarnings("ignore")

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    root = sys._MEIPASS
else:
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    root = os.path.abspath(os.path.join(cur_dir, os.pardir, os.pardir))
    src = os.path.abspath(os.path.join(cur_dir, os.pardir))
    sys.path.append(src)

tbl_cache = os.path.join(root, 'tbl_cache')
conn_path = os.path.join(root, 'conn.txt')

from access_database.access_db import AccessDataBase
from scraping.scraper import get_url
from scraping.crawler_oliveyoung import *
from errors import Errors
          
class ThreadCrawlingOlive(QtCore.QThread, QtCore.QObject):
    ''' Thread Crawling oliveyoung products '''
    
    def __init__(self, parent=None):
        super().__init__()
        self.power = False
        
        # path
        self.urls_path = os.path.join(tbl_cache, 'urls.txt')
        self.info_df_path = os.path.join(tbl_cache, 'info_df.csv')
        self.infos_path = os.path.join(tbl_cache, 'infos.txt')
        self.reviews_path = os.path.join(tbl_cache, 'reviews.txt')
        self.errors_path = os.path.join(tbl_cache, 'errors.txt')
        self.info_detail_df_path = os.path.join(tbl_cache, 'info_detail_df.csv')
        self.review_df_path = os.path.join(tbl_cache, 'review_df.csv')
        
        # db 연결
        with open(conn_path, 'rb') as f:
            conn = pickle.load(f)
        self.db = AccessDataBase(conn[0], conn[1], conn[2])
        
        # error class
        self.err = Errors()
    
    def _upload(self, comp=False):
        
        # save file 
        with open(self.infos_path, 'wb') as f:
            pickle.dump(self.infos, f)
        with open(self.reviews_path, 'wb') as f:
            pickle.dump(self.reviews, f)
        with open(self.errors_path, 'wb') as f:
            pickle.dump(self.errors, f)
            
        if (len(self.infos) != 0) & (len(self.reviews) != 0):
            # info table
            columns = [
                'product_url', 'product_name', 'brand_name', 'brand_code', 'brand_url', 
                'selection', 'division', 'groups',
                'price', 'sale_price', 'product_rating', 
                'product_size', 'skin_type', 'expiration_date', 
                'how_to_use', 'manufacturer', 'manufactured_country', 
                'ingredients_all', 'status']
            info_detail_df = pd.DataFrame(self.infos, columns=columns)
            info_detail_df.to_csv(self.info_detail_df_path, index=False)
            
            # reivew table
            columns = ['product_url', 'user_id', 'product_rating', 'review_date', 'product_review']
            review_df = pd.DataFrame(self.reviews, columns=columns)
            review_df.loc[review_df.product_review==''] = np.nan
            # review_df.to_csv(self.review_df_path, index=False)
            
            # merge
            info_df = pd.read_csv(self.info_df_path)
            info_df_mer = info_df.merge(info_detail_df, on='product_url', how='right')
            rev_df_mer = info_df.merge(review_df, on='product_url', how='right')
            
            # id & regist_date
            info_final_v = self.db.get_tbl('oliveyoung_product_info_final_version', ['id'])
            start_id = info_final_v.id.tolist()[-1] + 1
            info_df_mer.loc[:, 'id'] = range(start_id, len(info_df_mer) + start_id)
            rev_df_mer_mapped = info_df_mer.loc[:, ['id', 'product_code']].merge(rev_df_mer, on='product_code', how='right')
            
            # dedup
            rev_df_mer_mapped_dedup = rev_df_mer_mapped.drop_duplicates(keep='first', ignore_index=True)
            rev_df_mer_mapped_dedup = rev_df_mer_mapped_dedup.loc[rev_df_mer_mapped_dedup.product_review.notnull()].reset_index(drop=True)
            
            # regist_date
            regist_date = pd.Timestamp(datetime.today().strftime("%Y-%m-%d"))
            info_df_mer.loc[:, 'regist_date'] = regist_date
            rev_df_mer_mapped_dedup.loc[:, 'regist_date'] = regist_date
            
            if comp:
                try:
                    # upload table
                    self.db.engine_upload(info_df_mer, 'oliveyoung_product_info_final_version', 'append')
                    self.db.engine_upload(rev_df_mer_mapped_dedup, 'oliveyoung_product_info_final_version_review', 'append')
                    print("Oliveyoung update complete")
                    
                    # init cache file
                    os.remove(self.infos_path)
                    os.remove(self.reviews_path)
                    os.remove(self.errors_path)
                        
                except Exception as e:
                    # db 연결 끊김: VPN 연결 해제 및 와이파이 재연결 필요
                    print(f'\n\nError: {str(e)}\n\n')
                    if self.power:
                        self.stop()
        
    progress = QtCore.pyqtSignal(object)
    def run(self):
        ''' Run Thread '''
        
        with open(self.urls_path, 'rb') as f:
            urls = pickle.load(f)
            
        if os.path.exists(self.infos_path):
            with open(self.infos_path, 'rb') as f:
                self.infos = pickle.load(f)
        else:
            self.infos = []
        
        if os.path.exists(self.reviews_path):
            with open(self.reviews_path, 'rb') as f:
                self.reviews = pickle.load(f)
        else:
            self.reviews = []
        
        if os.path.exists(self.errors_path):
            with open(self.errors_path, 'rb') as f:
                self.errors = pickle.load(f)
        else:
            self.errors = []
        
        idx = 0
        t = tqdm(urls)
        for url in t:
            if self.power:
                self.progress.emit(t)
                
                # errors log
                try:
                    self.infos, self.reviews, self.errors = crawling_oliveyoung(url, self.infos, self.reviews, self.errors)
                except:
                    self.err.errors_log(url)
                
                idx += 1
            else:
                break
            
        # save ipunt data into cache dir
        with open(self.urls_path, 'wb') as f:
            pickle.dump(urls[idx:], f)
        
        if idx == len(urls):
            # Thread completion
            self._upload(comp=True)
        else:
            # upload table into db 
            self._upload()
            
        self.progress.emit(t)
        self.power = False
        
    def stop(self):
        ''' Stop Thread '''
        
        self.power = False
        self.quit()
        self.wait(3000)
        
class ThreadCrawlingOliveUrl(QtCore.QThread, QtCore.QObject):
    ''' Thread Crawling oliveyoung products '''
    
    def __init__(self, parent=None):
        super().__init__()
        self.power = False
        
        # path
        self.category_ids_path = os.path.join(tbl_cache, 'category_ids.txt')
        self.urls_path = os.path.join(tbl_cache, 'urls.txt')
        self.info_df_path = os.path.join(tbl_cache, 'info_df.csv')
        
        # db 연결
        with open(conn_path, 'rb') as f:
            conn = pickle.load(f)
        self.db = AccessDataBase(conn[0], conn[1], conn[2])
        
        # error class
        self.err = Errors()
        
    def _upload(self):
        
        if len(self.status) == 0:
            pass
        else:
            columns = ['url', 'status']
            status_df = pd.DataFrame(self.status, columns=columns)
            self.db.engine_upload(upload_df=status_df, table_name='oliveyoung_url_status', if_exists_option='append')

        columns = ['product_code', 'product_name', 'product_url', 'brand_name', 'price', 'sale_price', 'status']
        info_df = pd.DataFrame(self.infos, columns=columns).drop_duplicates('product_code', keep='first', ignore_index=True)
        path = os.path.join(tbl_cache, '_info_df.csv')
        info_df.to_csv(path, index=False)
        
        # dup check
        product_code = self.db.get_tbl('oliveyoung_product_info_final_version', ['product_code'])
        df_concat = pd.concat([product_code, info_df.loc[:, ['product_code']]])
        df_dup = df_concat[df_concat.duplicated('product_code', keep=False)].drop_duplicates('product_code', keep='first')
        df_dedup = pd.concat([info_df.loc[:, ['product_code']], df_dup]).drop_duplicates('product_code', keep=False)
        product_code_dedup = df_dedup.product_code.tolist()
        info_df_dedup = info_df.loc[info_df.product_code.isin(product_code_dedup), ['product_code', 'product_url']]
        info_df_dedup.to_csv(self.info_df_path, index=False)
        
        # urls 
        urls = info_df_dedup.product_url.tolist()
        with open(self.urls_path, 'wb') as f:
            pickle.dump(urls, f)
    
    progress = QtCore.pyqtSignal(object)
    def run(self):
        
        with open(self.category_ids_path, 'rb') as f:
            category_ids = pickle.load(f)
        
        self.infos, self.status = [], [] 
        t = tqdm(category_ids)
        for category_id in t:
            if self.power:
                self.progress.emit(t)
                
                selection = category_id[0:5]
                division = category_id[5:9]
                cnt = None
                try:
                    cnt = scraper_prd_cnt(category_id, page=1)
                except:
                    page = 1
                    url = f'https://www.oliveyoung.co.kr/store/display/getMCategoryList.do?dispCatNo=1000001{selection}{division}&fltDispCatNo=&prdSort=01&pageIdx={page}&rowsPerPage=24&searchTypeSort=btn_thumb&plusButtonFlag=N&isLoginCnt=0&aShowCnt=0&bShowCnt=0&cShowCnt=0&trackingCd=Cat1000001{selection}{division}_Small'
                    self.err.errors_log(url)
                
                if cnt is None:
                    pass
                elif cnt == -1:
                    pass
                else:
                    pages = cnt // 24 + 1
                    for page in range(1, pages + 1):
                        status = None
                        url = f'https://www.oliveyoung.co.kr/store/display/getMCategoryList.do?dispCatNo=1000001{selection}{division}&fltDispCatNo=&prdSort=01&pageIdx={page}&rowsPerPage=24&searchTypeSort=btn_thumb&plusButtonFlag=N&isLoginCnt=0&aShowCnt=0&bShowCnt=0&cShowCnt=0&trackingCd=Cat1000001{selection}{division}_Small'
                        try:
                            info, status = scraper_prd_info(category_id, page)
                        except:
                            self.err.errors_log(url)
                        
                        if status is None:
                            status = -2
                        elif status == -1:
                            pass
                        else:
                            self.infos += info
                        
                        self.status.append([url, status])
            else:
                break
        
        self._upload()    
        self.progress.emit(t)
        self.power = False
                
    def stop(self):
        ''' Stop Thread '''
        
        self.power = False
        self.quit()
        self.wait(3000)