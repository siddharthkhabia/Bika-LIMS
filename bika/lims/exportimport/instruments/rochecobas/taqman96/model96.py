""" Roche Cobas Taqman 96
"""
from bika.lims import bikaMessageFactory as _
from bika.lims.utils import t
from . import RocheCobasTaqman96CSVParser, RocheCobasTaqman96Importer
import json
import traceback

title = "Roche Cobas - Taqman - 96"

def Import(context, request):
    """ Beckman Coulter Access 2 analysis results
    """
    infile = request.form['rochecobas_taqman_model96_file']
    fileformat = request.form['rochecobas_taqman_model96_format']
    artoapply = request.form['rochecobas_taqman_model96_artoapply']
    override = request.form['rochecobas_taqman_model96_override']
    sample = request.form.get('rochecobas_taqman_model96_sample',
                              'requestid')
    instrument = request.form.get('rochecobas_taqman_model96_instrument', None)
    errors = []
    logs = []
    warns = []
    parser = None
    if not hasattr(infile, 'filename'):
        errors.append(_("No file selected"))
    if fileformat == 'csv':
        parser = RocheCobasTaqman96CSVParser(infile)
    else:
        errors.append(t(_("Unrecognized file format ${fileformat}",
                          mapping={"fileformat": fileformat})))

    if parser:
        status = ['sample_received', 'attachment_due', 'to_be_verified']
        if artoapply == 'received':
            status = ['sample_received']
        elif artoapply == 'received_tobeverified':
            status = ['sample_received', 'attachment_due', 'to_be_verified']

        over = [False, False]
        if override == 'nooverride':
            over = [False, False]
        elif override == 'override':
            over = [True, False]
        elif override == 'overrideempty':
            over = [True, True]

        sam = ['getRequestID', 'getSampleID', 'getClientSampleID']
        if sample == 'requestid':
            sam = ['getRequestID']
        if sample == 'sampleid':
            sam = ['getSampleID']
        elif sample == 'clientsid':
            sam = ['getClientSampleID']
        elif sample == 'sample_clientsid':
            sam = ['getSampleID', 'getClientSampleID']

        importer = RocheCobasTaqman96Importer(parser=parser,
                                              context=context,
                                              idsearchcriteria=sam,
                                              allowed_ar_states=status,
                                              allowed_analysis_states=None,
                                              override=over,
                                              instrument_uid=instrument)
        tbex = ''
        try:
            importer.process()
        except:
            tbex = traceback.format_exc()
        errors = importer.errors
        logs = importer.logs
        warns = importer.warns
        if tbex:
            errors.append(tbex)

    results = {'errors': errors, 'log': logs, 'warns': warns}

    return json.dumps(results)

class BeckmancoulterAccess2CSVParser(RocheCobasTaqman96CSVParser):
    def getAttachmentFileType(self):
        return "Roche Cobas Taqman 96"

class RocheCobasTaqman96Importer(RocheCobasTaqman96Importer):
    def getKeywordsToBeExcluded(self):
        return []