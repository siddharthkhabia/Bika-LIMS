from datetime import datetime
from bika.lims.exportimport.instruments.resultsimport import \
    AnalysisResultsImporter, InstrumentXLSXResultsFileParser

class EasyQXLSXParser(InstrumentXLSXResultsFileParser):
  def __init__(self, xlsx):
    InstrumentXLSXResultsFileParser.__init__(self,xlsx)
    self.columns = []
    self.resid = ''
    self.head_done = False

  def _parse_row(self,row_list):
    if row_list[0]=='Version' and not self.head_done :
      self.columns = row_list
      self.head_done =True
      return 0
    elif len(row_list)==len(columns) and self.head_done :
      """
      if we already have the headers and the list has
      the correct no of elements then parse it
      """
      rawdict= {}
      for i ,red in enumerate (row_list):
        rawdict[self.columns[i]] =red
        """
        default result added as the AU block of the file as 
        suggested by lemoene

        """
      rawdict['DefaulResult'] = 'Value'
      self.resid = rawdict['SampleID']
      if self.resid=="":
        self.resid = rawdict['SerialNumber']
        if self.resid=="":
          self.err("result identification not found")
          return -1

      self._addRawResult(self.resid,{testname: rawdict},False)
      return 0
    else :
      self.err("unexpected data format")
      return -1


class EasyQImporter(AnalysisResultsImporter):
    def __init__(self, parser, context, idsearchcriteria, override,
                 allowed_ar_states=None, allowed_analysis_states=None,
                 instrument_uid=None):
        AnalysisResultsImporter.__init__(self, parser, context,
                                         idsearchcriteria, override,
                                         allowed_ar_states,
                                         allowed_analysis_states,
                                         instrument_uid)

    