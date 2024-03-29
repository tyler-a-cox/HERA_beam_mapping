'''

Script to generate image from a measurement set using David's procedure

'''

import os
from casa import *
import numpy as np
import logging

#Create and configure logger
logging.basicConfig(filename="newfile.log",
                    format='%(asctime)s %(message)s',
                    filemode='w')

class CASA_Imaging:
    def __init__(self,config_data):
        self.gaintable = []
        self.logger = logging.getLogger()
    	if config_data['new_calibration'] == 'True':
            cal_params = config_data['new_cal_params']
            self.infile = cal_params['file_to_calibrate']
            self.kcal = cal_params['kcal']
            self.gcal = cal_params['gcal']
            self.model_name = cal_params['model_name']
            self.cal_sources = cal_params['cal_sources']
            self.clean_1_params = cal_params['clean_1']
            self.clean_2_params = cal_params['clean_2']
            self.clean_final_params = cal_params['clean_final']
            self.band_pass_1 = cal_params['band_pass_1']
            self.band_pass_2 = cal_params['band_pass_2']
            self.cal_flag = cal_params['flag']
            try:
                if self.cal_flag['autocorr'] == "True":
                    self.cal_flag["autocorr"] = True
                elif self.cal_flag["autocorr"] == "False":
                    self.cal_flag["autocorr"] = False
            except KeyError:
                self.logger.warning('Calibration key not found')

        else:
            self.gaintable = config_data['calibration_files']

        self.run_folder = config_data['data_path']['run_folder']
        self.img_folder = os.path.join(self.run_folder, config_data['data_path']['image_folder'])

        if not os.path.exists(self.run_folder):
            os.makedirs(self.run_folder)
        if not os.path.exists(self.img_folder):
            os.makedirs(self.img_folder)

    	self.final_clean_params = config_data['clean']
    	self.flag_params = config_data['flag']

    	try:
        	if self.flag_params['autocorr'] == "True":
        		self.flag_params['autocorr'] = True
        	elif self.flag_params['autocorr'] == "False":
        		self.flag_params['autocorr'] = False
    	except KeyError:
        	self.logger.warning('Calibration key not found')

    def _calname(self,m,c):
        '''
        Returns the file name for the new calibration file to be generated

        Parameters
        ----------
        m : str
            input measurement set file name
        c : str
            calibration being done

        Returns
        -------
        str
            file name of the new calibration file
        '''
        return (os.path.basename(m)+c+".cal")

    def _flag(self,infile):
        '''
        Flags the data in a measurement set using auto-correlations

        Parameters
        ----------
        infile : str
            input measurement set file name
        '''
        flagdata(infile, autocorr=True)

    def _gaincal(self, infile, kcal=None, gcal=None):
        '''
        Creates the initial calibration files using a calibration model to applies
        that calibration to a measurement set

        Parameters
        ----------
        infile : str
            input measurement set file name
        cal : str
            file name of the calibration model
            default: GC.cl (galactic model)

        Returns
        -------
        kc, gc : str
            file names of the new calibration files
        '''
        if kcal is None:
            kcal = self.kcal

        if gcal is None:
            gcal = self.gcal

        #create calibration files
        kc = os.path.join(self.run_folder,self._calname(infile, "K"))
        gaincal(infile, caltable=kc, gaintype='K', **kcal)

        #check for frequency errors
        gc = os.path.join(self.run_folder,self._calname(infile, "G"))
        gaincal(infile, caltable=gc, gaintype='G', gaintable=kc, **gcal)

        # Apply the calibration to the infile
        self._apply_cal(infile, [kc, gc])
        return (kc,gc)

    def _apply_cal(self,infile,gaintable = None):
        '''
        Applies a set of calibration files to a measurement set

        Parameters
        ----------
        infile : str
            input measurement set file name
        gaintable : str, list
            Takes a string or list of strings that are the file names of the
            calibration files being applied to the measurement sets

        '''
        if gaintable is None:
            gaintable = self.gaintable
        applycal(infile,gaintable=gaintable)

    def _split(self,infile,outfile,spw=""):
        '''
        Creates a measurement subset from an existing measurement set to trick casa
        to allow another calibration

        Parameters
        ----------
        infile : str
            input measurement set file name
        outfile : str
            output measurement set file name
        spw : str
            spectral window for the split to isolate
                default : ""
        '''
        split(infile, outfile, datacolumn="corrected", spw=spw)

    def _clean(self,infile, imgname,**kwargs):
        '''
        Deconvolves a measurement set and produces an image

        Parameters
        ----------
        infile : str
            input measurement set file name
        imgname : str
            file name of the output image files
        '''
        clean(vis=infile, imagename=imgname, **kwargs)

    def _band_pass(self,infile,**kwargs):
        '''
        Creates a bandpass calibration solution

        Parameters
        ----------
        infile : str
            input measurement set file name
        '''
        bc = self._calname(infile, "B")
    	bc = os.path.join(self.run_folder,bc)
    	bandpass(vis=infile, caltable=bc, solnorm=False, **kwargs)
        applycal(infile, gaintable=[bc])
        return (bc)

    def create_cal_files(self,infile=None):
        '''
        Runs the full processing algorithm including calibration file creation on
        a measurement set. This is used to calibrate subsequent files to an initial
        source

        Parameters
        ----------
        infile : str
            input measurement set file name
        img_dir : str
            directory name where image files are written
        '''
    	if infile is None:
    	    infile = self.infile
            run_dir = self.run_folder
            img_dir = self.img_folder

        self.logger.info('\nFlagging Data...\n')
        flagdata(infile, **self.cal_flag)

        self.logger.info('\nInitial Calibration...\n')
        kc, gc = self._gaincal(infile)
        imgname = os.path.join(run_dir,os.path.basename(infile)+ ".init.img")
        file_to_clean = os.path.join(run_dir,os.path.basename(infile) + "split" + ".ms")

        self.logger.info('\nSplitting Columns...\n')
        self._split(infile,file_to_clean)

        self.logger.info('\nCleaning Data...\n')
        clean(vis=file_to_clean,imagename=imgname, **self.clean_1_params)

        self.logger.info('\nRunning Band Pass...\n')
        bc = self._band_pass(file_to_clean, **self.band_pass_1)

        self.logger.info('\nSplitting Columns...\n')
        self._split(file_to_clean, file_to_clean + "c2.ms", spw="0:100~800")
        file_2_clean = file_to_clean + "c2.ms"
        imgname2 = file_to_clean +".init.img"

        self.logger.info('\nCleaning Data...\n')
        clean(vis=file_2_clean, imagename=imgname2, **self.clean_2_params)

        self.logger.info('\nRunning Band Pass...\n')
        bc1 = self._band_pass(file_2_clean, **self.band_pass_2)
        file_3_clean = file_2_clean
        imgnameFinal = infile + "Final.combined.img"
        imgnameFinal = os.path.join(img_dir,os.path.basename(imgnameFinal))

        self.logger.info('\nFinal Clean...\n')
        clean(vis=file_3_clean, imagename=imgnameFinal, **self.clean_final_params)

        self.gaintable = [kc,gc,bc,bc1]

    def make_image(self, infile, flag_params = None, cal_files = None, clean_params = None):
        '''
        Flags, calibrates, and cleans a measurement single measurement set

        Parameters
        ----------
        infile : str
            name of the measurement set to process
        gaintable : str, list
            string or list of strings of calibration file names to use to calibrate
            measurement sets
        '''

        if flag_params is None:
            flag_params = self.flag_params

        if cal_files is None:
            cal_files = self.gaintable

        if clean_params is None:
            clean_params = self.final_clean_params

        self.logger.info('Running File: ' + infile)
        img_dir = self.img_folder

        self.logger.info('\nFlagging Data...\n')
        flagdata(infile, **flag_params)

        self.logger.info('\nCalibrating Data...\n')

    	if len(cal_files) > 0:
            applycal(infile, gaintable=cal_files)

    	imgnameFinal = infile + 'Final.combined.img'
        imgnameFinal = os.path.join(img_dir,os.path.basename(imgnameFinal))

    	self.logger.info('\nCleaning...\n')
        clean(infile, imgnameFinal, **clean_params)

        exportfits(imagename=(imgnameFinal+'.image'),fitsimage=(imgnameFinal+'.fits'))
