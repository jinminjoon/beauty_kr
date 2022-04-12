import re
import os
import sys
import pickle
import pandas as pd

cur_dir = os.path.dirname(os.path.realpath(__file__))
root = os.path.abspath(os.path.join(cur_dir, os.pardir, os.pardir))
src = os.path.abspath(os.path.join(cur_dir, os.pardir))
sys.path.append(root)
sys.path.append(src)

from access_database import access_db
from mapping import preprocessing
from mapping.preprocessing import ThreadTitlePreprocess
from mapping import mapping_product
from mapping.mapping_product import ThreadComparing

from gui.get_table import GetDialog
from gui.table_view import TableViewer

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QListWidgetItem
from PyQt5.QtCore import Qt


if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS
    tbl_cache = os.path.join(base_path, 'tbl_cache_')
    
else:
    base_path = os.path.dirname(os.path.realpath(__file__))
    tbl_cache = os.path.join(root, 'tbl_cache')

conn_path = os.path.join(base_path, 'conn.txt')
form_path = os.path.join(base_path, 'form/mappingWindow.ui')

mapping_form = uic.loadUiType(form_path)[0]

class MappingWindow(QMainWindow, mapping_form):
    ''' Product Mapping Window '''
    
    def __init__(self):
        super().__init__()    
        self.setupUi(self)
        self.setWindowTitle('Mapping Products')
        # self.textBrowser.setOpenExternalLinks(True)
        self.viewer = None
        
        # db 연결
        with open(conn_path, 'rb') as f:
            conn = pickle.load(f)
        self.db = access_db.AccessDataBase(conn[0], conn[1], conn[2])
        
        # get table
        for table in self._get_tbl():
            item = QListWidgetItem(table)
            item.setCheckState(Qt.Unchecked)
            self.TableList.addItem(item)
            
        # self.view_table_name.clicked.connect(self.connect_dialog)
        
        self.Import.clicked.connect(self._import_tbl)
        self.view_table_0.clicked.connect(self._viewer_0)
        self.save_0.clicked.connect(self._save_0)
        
        # preprocessing
        self.thread_preprocess = ThreadTitlePreprocess()
        self.thread_preprocess.progress.connect(self.update_progress)
        self.preprocess.clicked.connect(self._preprocess)
        self.stop_preprocess.clicked.connect(self.thread_preprocess.stop)
        self.view_table_1.clicked.connect(self._viewer_1)
        self.save_1.clicked.connect(self._save_1)
        
        # comparing
        self.thread_compare = ThreadComparing()
        self.thread_compare.progress.connect(self._update_progress)
        self.compare.clicked.connect(self._comparing)
        self.stop_compare.clicked.connect(self.thread_compare.stop)
        self.view_table_2.clicked.connect(self._viewer_2)
        self.save_2.clicked.connect(self._save_2)
        
        # mapping
        self.mapping.clicked.connect(self._mapping)
        self.view_table_3.clicked.connect(self._viewer_3)
        self.save_3.clicked.connect(self._save_3)
        
        # mapping table
        self.mapping_table.clicked.connect(self._mapping_table)
        self.view_table_4.clicked.connect(self._viewer_4)
        self.save_4.clicked.connect(self._save_4)
        
    def update_progress(self, progress):
        
        prg_dict = progress.format_dict
        itm = prg_dict['n'] 
        tot = prg_dict['total']
        per = round((itm / tot) * 100, 0)
        elapsed = int(round(prg_dict['elapsed'], 0))
        if itm >= 1:
            remain_time = int(round((elapsed * tot / itm) - elapsed, 0))
        else:
            remain_time = 0
        
        self.pbar_0.setValue(per)
        
        message = f"{int(per)}% | Progress item: {itm}  Total: {tot} | Elapsed time: {elapsed}s < Remain time: {remain_time}s "
        self.statusbar.showMessage(message)
        
    def _update_progress(self, progress):
        
        prg_dict = progress.format_dict
        itm = prg_dict['n'] 
        tot = prg_dict['total']
        per = round((itm / tot) * 100, 0)
        elapsed = round(prg_dict['elapsed'], 0)
        if itm >= 1:
            remain_time = round((elapsed * tot / itm) - elapsed, 0)
        else:
            remain_time = 0
        
        self.pbar_1.setValue(per)
        
        elapsed_h = int(elapsed // 3600)
        elapsed_m = int((elapsed % 3600) // 60)
        elapsed_s = int(elapsed - (elapsed_h * 3600 + elapsed_m * 60))
        
        remain_h = int(remain_time // 3600)
        remain_m = int((remain_time % 3600) // 60)
        remain_s = int(remain_time - (remain_h * 3600 + remain_m * 60))
        
        message = f"{int(per)}% | Progress item: {itm}  Total: {tot} | Elapsed time: {elapsed_h}:{elapsed_m}:{elapsed_s} < Remain time: {remain_h}:{remain_m}:{remain_s} "
        self.statusbar.showMessage(message)
        
    # def connect_dialog(self):
    #     ''' Get.GetDialog connect '''    
        
    #     self.get = GetDialog()
    #     self.get.tables.connect(self.append_text)
    #     self.get.show()
            
    # def append_text(self, tables):
    #     self.textBrowser.clear()
    #     self.textBrowser.append(tables)
    
    def _get_tbl(self):
        ''' db에서 매핑 대상 테이블만 가져오기 '''
        
        tables = self.db.get_tbl_name()
        reg = re.compile('naver_beauty_product_info_extended_v[0-9]+')
        table_list = []
        for tbl in tables:
            tbl_ = re.match(reg, tbl)
            if tbl_:
                table_list.append(tbl_.group(0))
        table_list = sorted(list(set(table_list)))
        return table_list
        
    def _import_tbl(self):
        ''' 데이터 베이스에서 테이블 가져와서 통합하기 '''
        
        # 상품 매핑에 필요한 컬럼
        columns = ['id', 'brand_name', 'product_name', 'selection', 'division', 'groups']
        
        # 매핑 기준 테이블 
        tbl_0 = self.db.get_tbl('glowpick_product_info_final_version', columns)
        tbl_0.loc[:, 'table_name'] = 'glowpick_product_info_final_version'
        tbl_0.to_csv(tbl_cache + '/tbl_0.csv', index=False)
        
        # 매핑 대상 테이블
        tbls = []
        for idx in range(self.TableList.count()):
            if self.TableList.item(idx).checkState() == Qt.Checked:
                tbls.append(self.TableList.item(idx).text())
        
        
        if len(tbls) == 0:
            msg = QMessageBox()
            msg.setText(f'Please check the table')
            msg.exec_()
            
        else:
            tbl_1 = preprocessing.integ_tbl(self.db, tbls, columns)
            tbl_1.to_csv(tbl_cache + '/tbl_1.csv', index=False)
            msg = QMessageBox()
            msg.setText(f'Table import success')
            msg.exec_()
            
    def _preprocess(self):
        ''' 쓰레드 연결 및 전처리 수행 ''' 
        
        self.thread_preprocess.power = True
        self.thread_preprocess.start()
        
    def _comparing(self):
        ''' 쓰레드 연결 및 상품정보 비교 수행 '''
        
        self.thread_compare.power = True
        self.thread_compare.start()
        
    def _mapping(self):
        ''' Select mapped product '''
        
        compared_prds = pd.read_csv(tbl_cache + '/compared_prds.csv')
        mapped_prds = mapping_product.select_mapped_prd(compared_prds)
        mapped_prds.to_csv(tbl_cache + '/mapped_prds.csv', index=False)
        
        mapping_table = mapping_product.md_map_tbl(mapped_prds)
        mapping_table.to_csv(tbl_cache + '/mapping_table.csv', index=False)
        
    def _mapping_table(self):
        ''' Create mapping table'''
        mapped_prds = pd.read_csv(tbl_cache + '/mapped_prds.csv')
        mapping_table = mapping_product.md_map_tbl(mapped_prds)
        mapping_table.to_csv(tbl_cache + '/mapping_table.csv', index=False)
        
    def save_file(self, file_name):
        ''' 파일 저장하기 '''
        
        file_path = os.path.join(tbl_cache, file_name)
        df = pd.read_csv(file_path)
        
        # save_path = os.path.join(root, file_name)
        file_save = QFileDialog.getSaveFileName(self, "Save File", "", "csv file (*.csv)")
        
        if file_save[0] != "":
            df.to_csv(file_save[0], index=False)
            
    def tbl_viewer(self, file_name):
        ''' csv file viewer '''
        
        if self.viewer is None:
            self.viewer = TableViewer()
        else:
            self.viewer.close()
            self.viewer = TableViewer()
            
        self.viewer.show()
        self.viewer._loadFile(file_name)    
            
    def _save_0(self):
        file_name = "tbl_1.csv"
        self.save_file(file_name)
        
    def _save_1(self):
        file_name = "deprepro_1.csv"
        self.save_file(file_name)

    def _save_2(self):
        file_name = "compared_prds.csv"
        self.save_file(file_name)
        
    def _save_3(self):
        file_name = "mapped_prds.csv"
        self.save_file(file_name)

    def _save_4(self):
        file_name = "mapping_table.csv"
        self.save_file(file_name)
        
    def _viewer_0(self):
        file_name = "tbl_1.csv"
        self.tbl_viewer(file_name)
        
    def _viewer_1(self):
        file_name = "deprepro_1.csv"
        self.tbl_viewer(file_name)

    def _viewer_2(self):
        file_name = "compared_prds.csv"
        self.tbl_viewer(file_name)
        
    def _viewer_3(self):
        file_name = "mapped_prds.csv"
        self.tbl_viewer(file_name)

    def _viewer_4(self):
        file_name = "mapping_table.csv"
        self.tbl_viewer(file_name)
        