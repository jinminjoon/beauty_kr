import os
import sys
import pickle
import pandas as pd
from datetime import datetime

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QFileDialog

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
form_path = os.path.join(form_dir, 'crawlingGlInfoRevWindow.ui')
form = uic.loadUiType(form_path)[0]

from access_database.access_db import AccessDataBase
from multithreading.thread_crawling_glowpick import ThreadCrawlingGl
from multithreading.thread_crawling_glowpick import ThreadCrawlingProductCode
from gui.table_view import TableViewer

class CrawlingGlWindow(QMainWindow, form):
    ''' Product Info Crawling Window '''
    
    def __init__(self):
        super().__init__()    
        self.setupUi(self)
        self.setWindowTitle('Update Glowpick Products')
        self.viewer = None
        
        # file path
        self.file_path = os.path.join(tbl_cache, 'product_codes.txt')
        self.selections = os.path.join(tbl_cache, 'selections.txt')
        self.divisions = os.path.join(tbl_cache, 'divisions.txt')
        self.selection_idx = os.path.join(tbl_cache, 'selection_idx.txt')
        self.division_idx = os.path.join(tbl_cache, 'division_idx.txt')
        self.path_scrape_df = os.path.join(tbl_cache, 'gl_info.csv')
        self.path_scrape_df_rev = os.path.join(tbl_cache, 'gl_info_rev.csv')
        self.path_prg = os.path.join(tbl_cache, 'prg_dict.txt')
        
        # init class
        self.thread_crw = ThreadCrawlingGl()
        self.thread_code = ThreadCrawlingProductCode()
        
        # connect thread
        self.thread_crw.progress.connect(self.update_progress)
        self.thread_code.progress.connect(self._update_progress)
         
        # connect func & btn
        self.Select.clicked.connect(self._select)
        self.Run_2.clicked.connect(self._run_prd_codes)
        self.Run.clicked.connect(self._run_crawling)
        self.Stop.clicked.connect(self.thread_code.stop)
        self.Pause.clicked.connect(self.thread_crw.stop)
        self.View.clicked.connect(self.tbl_viewer)
        self.Save.clicked.connect(self.save_file)
        self.Upload.clicked.connect(self._upload_df)
        
        # connect db
        with open(conn_path, 'rb') as f:
            conn = pickle.load(f)
        self.db = AccessDataBase(conn[0], conn[1], conn[2])
        
        # table name
        self.table_name_info = "glowpick_product_info_final_version_temp"
        self.table_name_rev = "glowpick_product_info_final_version_review_temp"
        
        # category toggled
        self.skincare.setChecked(False)
        self.skincare.toggled.connect(self.categ_toggled)
        self.bodycare.setChecked(False)
        self.bodycare.toggled.connect(self.categ_toggled)
        self.makeup.setChecked(False)
        self.makeup.toggled.connect(self.categ_toggled)
        self.haircare.setChecked(False)
        self.haircare.toggled.connect(self.categ_toggled)
        self.cleansing.setChecked(False)
        self.cleansing.toggled.connect(self.categ_toggled)
        self.menscare.setChecked(False)
        self.menscare.toggled.connect(self.categ_toggled)
        self.suncare.setChecked(False)
        self.suncare.toggled.connect(self.categ_toggled)
        self.maskpack.setChecked(False)
        self.maskpack.toggled.connect(self.categ_toggled)
        
    def update_progress(self, progress):
        
        if os.path.isfile(tbl_cache + '/prg_dict.txt'):
            with open(tbl_cache + '/prg_dict.txt', 'rb') as f:
                prg_dict_ = pickle.load(f)
            itm_ = prg_dict_['n'] 
            elapsed_ = round(prg_dict_['elapsed'], 0)
            
        else:
            itm_, elapsed_ = 0, 0
        
        prg_dict = progress.format_dict
        itm = prg_dict['n'] + itm_
        tot = prg_dict['total'] + itm_ 
        per = int(round((itm / tot) * 100, 0))
        elapsed = round(prg_dict['elapsed'], 0) + elapsed_
        prg_dict_ = {
            'n': itm,
            'elapsed': elapsed,
        }
                
        if itm >= 1:
            remain_time = round((elapsed * tot / itm) - elapsed, 0)
        else:
            remain_time = 0
        
        self.progressBar.setValue(per)
        
        elapsed_h = int(elapsed // 3600)
        elapsed_m = int((elapsed % 3600) // 60)
        elapsed_s = int(elapsed - (elapsed_h * 3600 + elapsed_m * 60))
        
        remain_h = int(remain_time // 3600)
        remain_m = int((remain_time % 3600) // 60)
        remain_s = int(remain_time - (remain_h * 3600 + remain_m * 60))
        
        message = f"{per}% | Progress item: {itm}  Total: {tot} | Elapsed time: {elapsed_h}:{elapsed_m}:{elapsed_s} < Remain time: {remain_h}:{remain_m}:{remain_s}"
        self.statusbar.showMessage(message)
        
        # pause ?????? ???????????? ????????? ??????
        if not self.thread_crw.power:
            with open(tbl_cache + '/prg_dict.txt', 'wb') as f:
                pickle.dump(prg_dict_, f)
            
            if itm == tot:
                message = f"{per}% | Progress item: {itm}  Total: {tot} | Elapsed time: {elapsed_h}:{elapsed_m}:{elapsed_s} < Remain time: {remain_h}:{remain_m}:{remain_s} **Complete**"
                os.remove(self.path_prg)
            else:
                message = f"{per}% | Progress item: {itm}  Total: {tot} | Elapsed time: {elapsed_h}:{elapsed_m}:{elapsed_s} < Remain time: {remain_h}:{remain_m}:{remain_s} **PAUSE**"
            self.statusbar.showMessage(message)
        
        # ip ?????? ??? db ?????? ?????? ??????
        if self.thread_crw.check == 1:
            msg = QMessageBox()
            msg.setText("\n    ** ip ????????? **\n\n - VPN ???????????? ??????\n - wifi ????????? ??????")
            msg.exec_()
        elif self.thread_crw.check == 2:
            msg = QMessageBox()
            msg.setText("\n    ** db ?????? ?????? **\n\n - VPN, wifi ????????? ??????\n\n - Upload ?????? ?????? ??? re-Run")
            msg.exec_()
                
    def _update_progress(self, progress):
        
        prg_dict = progress.format_dict
        itm = prg_dict['n'] 
        tot = prg_dict['total']
        per = int(round((itm / tot) * 100, 0))
        elapsed = int(round(prg_dict['elapsed'], 0))
        if itm >= 1:
            remain_time = int(round((elapsed * tot / itm) - elapsed, 0))
        else:
            remain_time = 0
        
        self.progressBar_2.setValue(per)
        
        message = f"{per}% | Progress item: {itm}  Total: {tot} | Elapsed time: {elapsed}s < Remain time: {remain_time}s "
        self.statusbar.showMessage(message)
        
        if not self.thread_code.power:
            with open(self.file_path, 'rb') as f:
                product_codes = pickle.load(f)
            products = len(product_codes)
            time = round(products * 30 / 3600, 2)
            self.Products.display(products)
            self.Time.display(time)
        
    def categ_toggled(self):
        categs = []
        
        if self.skincare.isChecked():
            categ = "????????????"
            categs.append(categ)
            
        if self.bodycare.isChecked():
            categ = "??????&??????"
            categs.append(categ)
            
        if self.makeup.isChecked():
            categ_ = ["?????????????????????", "??????????????????", "???????????????"]
            for categ in categ_:
                categs.append(categ)
            
        if self.haircare.isChecked():
            categ = "??????"
            categs.append(categ)
            
        if self.cleansing.isChecked():
            categ = "?????????"
            categs.append(categ)
            
        if self.menscare.isChecked():
            categ = "???????????????"
            categs.append(categ)
            
        if self.suncare.isChecked():
            categ = "?????????"
            categs.append(categ)
            
        if self.maskpack.isChecked():
            categ = "?????????/???"
            categs.append(categ)
            
        if self.beauty_tool.isChecked():
            categ = "?????????"
            categs.append(categ)
            
        if self.fragrance.isChecked():
            categ = "???????????????"
            categs.append(categ)
            
        return categs
    
    def _select(self):
        selections = self.categ_toggled()
        if len(selections) == 0:
            msg = QMessageBox()
            msg.setText("** ?????? ????????? ??????????????? ??????????????? **")
            msg.exec_()
        
        else:            
            if self.checkBox.isChecked():
                df_mapped = self.thread_crw._get_tbl()
                while len(df_mapped) == 0:
                    msg = QMessageBox()
                    msg.setText("\n    ** db ?????? ?????? **\n\n - VPN, wifi ????????? ??????\n\n")
                    msg.exec_()
                    df_mapped = self.thread_crw._get_tbl()
                    
                df_mapped_categ = df_mapped.loc[df_mapped.selection.isin(selections)]
                product_codes = df_mapped_categ.product_code.unique().tolist()
                with open(self.file_path, 'wb') as f:
                    pickle.dump(product_codes, f)
                    
            else:            
                with open(self.selections, 'wb') as f:
                    pickle.dump(selections, f)
                    
                while True:
                    try:
                        gl = self.db.get_tbl('glowpick_product_info_final_version', ['selection', 'division'])
                        break
                    except:
                        msg = QMessageBox()
                        msg.setText("\n    ** db ?????? ?????? **\n\n - VPN, wifi ????????? ??????\n\n")
                        msg.exec_()
                
                divisions = []
                for sel in selections:
                    div = list(set(gl.loc[gl.selection==sel, 'division'].values.tolist()))
                    divisions += div
                with open(self.divisions, 'wb') as f:
                    pickle.dump(divisions, f)
                    
            msg = QMessageBox()
            msg.setText("Selection done!")
            msg.exec_()
            
    def _run_prd_codes(self):
        ''' Run crawling product codes thread '''
        if not self.thread_code.power:
            if os.path.isfile(self.selections):            
                msg = QMessageBox()
                msg.setText("- ????????? ?????? ?????? \n- VPN ?????? ?????? \n- mac ?????? ?????? ?????? ?????? \n ** ???????????? ????????? ??????: ??? 20??? ?????? ??????????????? **")
                msg.exec_()
                
                # get category index
                self.thread_code.find_category_index()
                if os.path.isfile(self.selection_idx):
                    with open(self.selection_idx, 'rb') as f:
                        selection_idx = pickle.load(f)
                        if len(selection_idx) == 0:
                            msg = QMessageBox()
                            msg.setText("\n    ** ip ????????? **\n\n - VPN ???????????? ??????\n - wifi ????????? ??????\n - re-Run ??????")
                            msg.exec_()
                        else:
                            # start thread
                            self.thread_code.power = True
                            self.thread_code.start()
                else:
                    msg = QMessageBox()
                    msg.setText("\n    ** ip ????????? **\n\n - VPN ???????????? ??????\n - wifi ????????? ??????\n - re-Run ??????")
                    msg.exec_()
                
            else:
                msg = QMessageBox()
                msg.setText("** Select ?????? ??? ??????????????? **")
                msg.exec_()
        else:
            pass
        
    def _run_crawling(self):
        ''' Run crawling products thread '''
        if not self.thread_crw.power:
            if os.path.isfile(self.file_path):
                msg = QMessageBox()
                msg.setText("- ????????? ?????? ?????? \n- VPN ?????? ?????? \n- mac ?????? ?????? ?????? ??????")
                msg.exec_()
                self.thread_crw.power = True
                self.thread_crw.start()
            else:
                msg = QMessageBox()
                msg.setText("** ?????? ???????????? ?????? ?????? ??? ??????????????? **")
                msg.exec_()    
        else:
            pass
        
    def save_file(self):
        ''' save csv file '''
        
        # ????????? ?????? ????????? ????????? ??? ??????
        if os.path.isfile(self.path_scrape_df):
            df = pd.read_csv(self.path_scrape_df)
            file_save = QFileDialog.getSaveFileName(self, "Save File", "", "csv file (*.csv)")
            
            if file_save[0] != "":
                df.to_csv(file_save[0], index=False)
        else:
            msg = QMessageBox()
            msg.setText('** ???????????? ??? ?????? ?????????????????? **')
            msg.exec_()
            
    def tbl_viewer(self):
        ''' table viewer '''
        
        # ????????? ???????????? ????????? ??? open table viewer
        if os.path.isfile(self.path_scrape_df):
            if self.viewer is None:
                self.viewer = TableViewer()
            else:
                self.viewer.close()
                self.viewer = TableViewer()
                
            self.viewer.show()
            self.viewer._loadFile('gl_info.csv')
        else:
            msg = QMessageBox()
            msg.setText('** ???????????? ??? ?????? ?????????????????? **')
            msg.exec_()
            
    def _upload_df(self):
        ''' upload table into db '''
        
        if os.path.exists(self.file_path):
            with open(self.file_path, 'rb') as f:
                product_codes = pickle.load(f)
            
            if len(product_codes) == 0:
                ck = self.thread_crw._upload_df(comp=True)
            else:
                ck = self.thread_crw._upload_df(comp=False)
        else:
            ck = self.thread_crw._upload_df(comp=True)
        
        # db connection check
        if ck == 1:
            table_name = 'glowpick_product_info_final_version'
            table_name_review = 'glowpick_product_info_final_version_review'
            msg = QMessageBox()
            msg.setText(f"<????????? ????????? ??????>\n- {table_name}\n- {table_name_review}")
            msg.exec_()
            
        elif ck == 2:
            msg = QMessageBox()
            msg.setText(f"\n    ** db ?????? ?????? **\n\n - {self.table_name_info}\n\n - {self.table_name_rev}")
            msg.exec_()
                    
        elif ck == -1:
            table_name = 'glowpick_product_info_final_version'
            msg = QMessageBox()
            msg.setText("\n    ** db ?????? ?????? **\n\n- Upload failed: {table_name}\n\n- VPN, wifi ????????? ??????\n\n- Upload ?????? ?????? ??? re-Run")
            msg.exec_()

        elif ck == -2:
            msg = QMessageBox()
            msg.setText(f"\n    ** db ?????? ?????? **\n\n- Upload failed: {self.table_name_info}\n\n- VPN, wifi ????????? ??????\n\n- Upload ?????? ?????? ??? re-Run")
            msg.exec_()