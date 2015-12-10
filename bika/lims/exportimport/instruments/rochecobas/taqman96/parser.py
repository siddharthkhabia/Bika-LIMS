from datetime import datetime
from bika.lims.exportimport.instruments.resultsimport import \
    AnalysisResultsImporter, InstrumentCSVResultsFileParser

class RocheCobasTaqman96CSVParser(InstrumentCSVResultsFileParser):
	"""docstring for RocheCobasTaqman96CSVParser"""
	def __init__(self , csv):
		InstrumentCSVResultsFileParser.__init__(self,csv)
		self.columns = []
		self.resid='' #to be passes in addRawResult()
		self.is_head = True

	def _parseline(self , line) :
		line_list=self.splitline(line)
		if len(line_list)>0 and self.is_head :
			self.columns=line_list
			self.is_head =False
		elif len(line_list)>0 and not self.is_head:
			self.parse_val_line(line_list)
		else:
			self.err("Invalid data format",numline=self._numline) #as in Roche Cobas Taqman 48 file.
			return -1

	def splitline(self , line):
		"""
			A seperate method is required to allow 
			entries like "10,000" in csv as pointed 
			out by rockfruit .
		"""
		count_inv = 0
		cline = ""
		for i in range(len(line)) :
			if line[i] == '"':
				count_inv = count_inv+1
			if line[i] == ",":
				if count_inv%2==1:
					cline = cline + "~/*"
				else:
					cline = cline + ","
			else:
				cline = cline + line[i]
		nline=cline.replace('"','').split(",")
		fline = []
		for word in nline :
			word=word.replace("~/*",",")
			fline.append(word)
		return fline

	def parse_val_line(self , line_list):
		if len(line_list) != len(self.columns):
			self.err("Invalid file , no of entries and header and values do not match")
			return -1
		list = {}
		for ind , value in enumerate (line_list):
			list[self.columns[ind]]=value
		self.resid = list['Sample ID']	
		if self.resid=="":
			self.resid=list['Order Number']
		if self.resid=="":
			self.err("Result identification not found",numline=self._numline) 
			return -1
		#the following checks error for Test name , not sure why the Test was deleted from the dictionary 
		#after checking that it is present
		#deleting for now. 
		list['DefaultResult']='Result'
		if list['Test']=='':
			self.err("Test name not found",numline=self._numline)
			return -1
		testname  = list['Test']
		list[DateTime]=self.csvDate2BikaDate(list['Accepted Date/Time'])
		self.addRawResult(resid,{testname : list},False)
		return 0

	def csvDate2BikaDate(self, DateTime):
			# example: 11/03/2014 14:46:46 --> %d/%m/%Y %H:%M %p
	        Date, Time = DateTime.split(' ')
	        dtobj = datetime.strptime(Date + ' ' + Time, "%Y/%m/%d %H:%M:%S")
	        return dtobj.strftime("%Y%m%d %H:%M:%S")