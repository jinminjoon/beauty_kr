import re
import os
import sys
import pickle
import pandas as pd

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QListWidgetItem
from PyQt5.QtCore import Qt

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    root = sys._MEIPASS
    form_dir = os.path.join(root, 'form')
else:
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    root = os.path.abspath(os.path.join(cur_dir, os.pardir, os.pardir))
    src = os.path.abspath(os.path.join(cur_dir, os.pardir))
    sys.path.append(src)
    form_dir = os.path.join(src, 'gui/form')
    
tbl_cache = os.path.join(root, 'tbl_cache')
conn_path = os.path.join(root, 'conn.txt')
form_path = os.path.join(form_dir, 'mappingWindow.ui')
form = uic.loadUiType(form_path)[0]

from access_database.access_db import AccessDataBase
from multithreading.thread_mapping import ThreadTitlePreprocess, ThreadMapping
from gui.table_view import TableViewer

class MappingWindow(QMainWindow, form):
    ''' Product Mapping Window '''
    
    def __init__(self):
        super().__init__()    
        self.setupUi(self)
        self.setWindowTitle('Mapping Products')
        self.viewer = None
        self.getter = False
        self.prepro = False
        self._prepro = False
        self.comp = False
        self._comp = False
        self.mapped = False
        
        # file path
        self.tbl = os.path.join(tbl_cache, 'tbl.csv')
    
        # db 연결
        with open(conn_path, 'rb') as f:
            conn = pickle.load(f)
        self.db = AccessDataBase(conn[0], conn[1], conn[2])
        
        # get table
        for table in self._get_tbl():
            item = QListWidgetItem(table)
            item.setCheckState(Qt.Unchecked)
            self.TableList.addItem(item)
        
        self.Import.clicked.connect(self._import_tbl)
        self.view_table_0.clicked.connect(self._viewer_0)
        self.save_0.clicked.connect(self._save_0)
        
        # preprocessing
        self.thread_preprocess = ThreadTitlePreprocess()
        self.thread_preprocess.progress.connect(self.update_progress)
        self.preprocess.clicked.connect(self._preprocess)
        self.view_table_1.clicked.connect(self._viewer_1)
        self.save_1.clicked.connect(self._save_1)
        
        # comparing
        self.thread_mapping = ThreadMapping()
        self.thread_mapping.progress.connect(self._update_progress)
        self.compare.clicked.connect(self._comparing)
        self.view_table_2.clicked.connect(self._viewer_2)
        self.save_2.clicked.connect(self._save_2)
        
        # mapping status
        self.status.clicked.connect(self._status)
        
        # upload table to db
        self.Upload.clicked.connect(self._upload)
        
    def update_progress(self, progress):
        
        prg_dict = progress.format_dict
        itm = prg_dict['n'] 
        tot = prg_dict['total']
        per = int(round((itm / tot) * 100, 0))
        elapsed = int(round(prg_dict['elapsed'], 0))
        if itm >= 1:
            remain_time = int(round((elapsed * tot / itm) - elapsed, 0))
        else:
            remain_time = 0
        
        self.pbar_0.setValue(per)
        
        message = f"{per}% | Progress item: {itm}  Total: {tot} | Elapsed time: {elapsed}s < Remain time: {remain_time}s "
        self.statusbar.showMessage(message)
        
    def _update_progress(self, progress):
        
        prg_dict = progress.format_dict
        itm = prg_dict['n'] 
        tot = prg_dict['total']
        per = int(round((itm / tot) * 100, 0))
        elapsed = round(prg_dict['elapsed'], 0)
        if itm >= 1:
            remain_time = round((elapsed * tot / itm) - elapsed, 0)
        else:
            remain_time = 0
        
        self.pbar_1.setValue(per)
        message = f"{per}% | Progress item: {itm}  Total: {tot} | Elapsed time: {elapsed}s < Remain time: {remain_time}s "
        self.statusbar.showMessage(message)
    
    def _get_tbl(self):
        ''' db에서 매핑 대상 테이블만 가져오기 '''
        
        tables = self.db.get_tbl_name()
        # naver
        reg = re.compile('naver_beauty_product_info_extended_v[0-9]+')
        table_list = []
        for tbl in tables:
            tbl_ = re.match(reg, tbl)
            if tbl_:
                table_list.append(tbl_.group(0))
        table_list = sorted(list(set(table_list)))
        table_list.append('naver_beauty_product_info_final_version')
        
        # oliveyoung
        table_list.append('oliveyoung_product_info_final_version')
    
        # lalavla
        # table_list.append('lalavla_product_info_final_version')
        
        return table_list
    
    def _import_tbl(self):
        ''' 데이터 베이스에서 테이블 가져와서 통합하기 '''
        
        # 상품 매핑에 필요한 컬럼
        
        columns = ['id', 'brand_name', 'product_name', 'selection', 'division', 'groups']
        
        # 매핑 기준 테이블 
        tbl_0 = self.db.get_tbl('glowpick_product_info_final_version', columns + ['dup_check'])
        tbl_0.loc[:, 'table_name'] = 'glowpick_product_info_final_version'
        # dedup
        tbl_0 = tbl_0.loc[tbl_0.dup_check != -1].reset_index(drop=True)
        tbl_0 = tbl_0.drop(columns='dup_check')
        
        # 매핑 대상 테이블
        tbls = []
        for idx in range(self.TableList.count()):
            if self.TableList.item(idx).checkState() == Qt.Checked:
                tbls.append(self.TableList.item(idx).text())
        
        if len(tbls) == 0:
            msg = QMessageBox()
            msg.setText(f'매핑 대상 테이블을 선택하세요')
            msg.exec_()
            
        else:
            tbl_1 = self.db.integ_tbl(tbls, columns)
            df_concat = pd.concat([tbl_0, tbl_1]).reset_index(drop=True)
            df_concat.to_csv(self.tbl, index=False)
            
            msg = QMessageBox()
            msg.setText(f'Table import success!')
            msg.exec_()
            self.getter = True
            
    def _preprocess(self):
        ''' 쓰레드 연결 및 전처리 수행 ''' 
        if self.getter:    
            if not self.thread_preprocess.power:
                # category reclassify & title preprocess
                
                # run thread
                self.thread_preprocess.power = True
                self.thread_preprocess.start()
                self.prepro = True
                self.getter = False
            else:
                pass
        else:
            msg = QMessageBox()
            msg.setText(f'매핑 대상 테이블 임포트 완료 후 시도하세요')
            msg.exec_()
            
    def _comparing(self):
        ''' 쓰레드 연결 및 상품정보 비교 수행 '''
        if self.prepro:
            if not self.thread_mapping.power:
                # run thread
                self.thread_mapping.power = True
                self.thread_mapping.start()
                self.prepro = False
                self.comp = True
            else:
                pass
        else:
            msg = QMessageBox()
            msg.setText(f'매핑 대상 테이블 전처리 완료 후 시도하세요')
            msg.exec_()
            
    def save_file(self, file_name):
        ''' save csv file '''
        
        file_path = os.path.join(tbl_cache, file_name)
        # 캐시에 해당 파일이 존재할 때 저장
        if os.path.isfile(file_path):
            df = pd.read_csv(file_path, lineterminator='\n')
            file_save = QFileDialog.getSaveFileName(self, "Save File", "", "csv file (*.csv)")
            
            if file_save[0] != "":
                df.to_csv(file_save[0], index=False)
        else:
            msg = QMessageBox()
            msg.setText(self.msg)
            msg.exec_()
            
    def tbl_viewer(self, file_name):
        ''' table viewer '''
        
        # 캐시에 테이블이 존재할 때 open table viewer 
        file_path = os.path.join(tbl_cache, file_name)
        if os.path.isfile(file_path):
            if self.viewer is None:
                self.viewer = TableViewer()
            else:
                self.viewer.close()
                self.viewer = TableViewer()
                
            self.viewer.show()
            self.viewer._loadFile(file_name)
        else:
            msg = QMessageBox()
            msg.setText(self.msg)
            msg.exec_()    
            
    def _save_0(self):
        file_name = "tbl.csv"
        self.msg = "테이블 가져오기 완료 후 시도하세요"
        self.save_file(file_name)
        
    def _save_1(self):
        file_name = "tbl_deprepro.csv"
        self.msg = "전처리 완료 후 시도하세요"
        self.save_file(file_name)

    def _save_2(self):
        file_name = "mapping_table.csv"
        self.msg = "매핑 완료 후 시도하세요"
        self.save_file(file_name)
        
    def _viewer_0(self):
        file_name = "tbl.csv"
        self.msg = "테이블 가져오기 완료 후 시도하세요"
        self.tbl_viewer(file_name)
        
    def _viewer_1(self):
        file_name = "tbl_deprepro.csv"
        self.msg = "전처리 완료 후 시도하세요"
        self.tbl_viewer(file_name)

    def _viewer_2(self):
        file_name = "mapping_table.csv"
        self.msg = "매핑 완료 후 시도하세요"
        self.tbl_viewer(file_name)
        
    def _status(self):
        file_name = "mapping_table.csv"
        file_path = os.path.join(tbl_cache, file_name)
        if os.path.isfile(file_path):
            mapping_table = pd.read_csv(file_path)
            mapped_product_count = len(mapping_table.item_key.unique())
            mapping_product_count = len(mapping_table)
            QMessageBox.about(self,
                            'Mapping Status',
                            f"** Perfect Mapping Completion ** \n- 매핑 기준 상품 수(글로우픽): {mapped_product_count}\n- 매핑 대상 상품 수: {mapping_product_count}\n")        
        else:
            msg = QMessageBox()
            msg.setText(f'매핑 완료 후 시도하세요')
            msg.exec_()
            
    def _upload(self):
        file_name = "mapping_table.csv"
        file_path = os.path.join(tbl_cache, file_name)
        msg = QMessageBox()
        if os.path.isfile(file_path):
            mapping_table = pd.read_csv(file_path)
        
            # upload table to db
            self.db.create_table(upload_df=mapping_table, table_name='beauty_kr_mapping_table')
            msg.setText("\n    ** db 업로드 완료 **\n\n- beauty_kr_mapping_table")
            msg.exec_()
        else:
            msg.setText(f'매핑 완료 후 시도하세요')
            msg.exec_()