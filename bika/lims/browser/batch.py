from AccessControl import getSecurityManager
from DateTime import DateTime
from Products.AdvancedQuery import Or, MatchRegexp, Between
from Products.Archetypes.config import REFERENCE_CATALOG
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from bika.lims import PMF, logger, bikaMessageFactory as _
from bika.lims.browser import BrowserView
from bika.lims.browser.analysisrequest import AnalysisRequestWorkflowAction, \
    AnalysisRequestsView, AnalysisRequestAddView
from bika.lims.browser.bika_listing import BikaListingView
from bika.lims.browser.client import ClientAnalysisRequestsView, \
    ClientSamplesView
from bika.lims.browser.publish import Publish
from bika.lims.browser.sample import SamplesView
from bika.lims.idserver import renameAfterCreation
from bika.lims.interfaces import IContacts
from bika.lims.permissions import *
from bika.lims.subscribers import doActionFor, skip
from bika.lims.utils import isActive
from operator import itemgetter
from plone.app.content.browser.interfaces import IFolderContentsView
from plone.app.layout.globals.interfaces import IViewView
from zope.i18n import translate
from zope.interface import implements
from zope.cachedescriptors.property import Lazy as lazy_property
import json
import plone

class BatchAnalysisRequestsView(AnalysisRequestsView, AnalysisRequestAddView):
    template = ViewPageTemplateFile("templates/analysisrequests.pt")
    ar_add = ViewPageTemplateFile("templates/ar_add.pt")
    def __init__(self, context, request):
        super(BatchAnalysisRequestsView, self).__init__(context, request)
        self.contentFilter['getBatchUID'] = self.context.UID()

    def __call__(self):
        self.context_actions = {}
        bc = getToolByName(self.context, 'bika_catalog')
        wf = getToolByName(self.context, 'portal_workflow')
        mtool = getToolByName(self.context, 'portal_membership')
        addPortalMessage = self.context.plone_utils.addPortalMessage
        if isActive(self.context):
            if mtool.checkPermission(AddAnalysisRequest, self.portal):
                self.context_actions[self.context.translate(_('Add new'))] = {
                    'url':self.context.absolute_url() + '/ar_add?col_count=1',
                    'icon': '++resource++bika.lims.images/add.png'}
        return super(BatchAnalysisRequestsView, self).__call__()

    @lazy_property

    def Client(self):
        bc = getToolByName(self.context, 'bika_catalog')
        proxies = bc(portal_type="AnalysisRequest", getBatchUID=self.context.UID())
        if proxies:
            return proxies[0].getObject()

    def getMemberDiscountApplies(self):
        client = self.Client
        return client and client.getMemberDiscountApplies() or False

    def getRestrictedCategories(self):
        client = self.Client
        return client and client.getRestrictedCategories() or []

    def getDefaultCategories(self):
        client = self.Client
        return client and client.getDefaultCategories() or []

class BatchSamplesView(SamplesView):
    def __init__(self, context, request):
        super(BatchSamplesView, self).__init__(context, request)
        self.view_url = self.context.absolute_url() + "/samples"
        if 'path' in self.contentFilter:
            del(self.contentFilter['path'])

    def contentsMethod(self, contentFilter):
        tool = getToolByName(self.context, self.catalog)
        state = [x for x in self.review_states if x['id'] == self.review_state][0]
        for k,v in state['contentFilter'].items():
            self.contentFilter[k] = v
        tool_samples = tool(contentFilter)
        samples = {}
        for sample in (p.getObject() for p in tool_samples):
            for ar in sample.getAnalysisRequests():
                if ar.getBatchUID() == self.context.UID():
                    samples[sample.getId()] = sample
        return samples.values()

class ajaxGetBatchInfo(BrowserView):
    """ Grab the details for Doctor, Patient, Hospital (Titles).
    These are displayed onload next to the ID fields, but they are not part of the schema.
    """
    def __call__(self):
        plone.protect.CheckAuthenticator(self.request)

        batch = self.context
        patientids = ''
        client = self.portal_catalog(portal_type='Client', UID=batch.getClientUID())
        if client:
            client = client[0].getObject()
        patient = self.bika_patient_catalog(portal_type='Patient', UID=batch.getPatientUID())
        if patient:
            patient = patient[0].getObject()
            patientids = len(patient.getPatientIdentifiersStr()) > 0 and "("+patient.getPatientIdentifiersStr()+")" or ''
        doctor = self.portal_catalog(portal_type='Doctor', UID=batch.getDoctorUID())
        if doctor:
            doctor = doctor[0].getObject()

        ret = {'Client': client and "<a href='%s/edit'>%s</a>"%(client.absolute_url(), client.Title()) or '',
               'Patient': patient and "<a href='%s/edit'>%s</a> %s"%(patient.absolute_url(), patient.Title(), patientids) or '',
               'Doctor': doctor and "<a href='%s/edit'>%s</a>"%(doctor.absolute_url(), doctor.Title()) or ''}

        return json.dumps(ret)

class ajaxGetAetiologicAgents(BrowserView):
    """ Aetologic Agents from site setup
    """
    def __call__(self):
        plone.protect.CheckAuthenticator(self.request)
        title = 'title' in self.request and self.request['title'] or ''
        uid = 'uid' in self.request and self.request['uid'] or ''
        searchTerm = (len(title)==0 and 'searchTerm' in self.request) and self.request['searchTerm'].lower() or title.lower()
        page = 'page' in self.request and self.request['page'] or 1
        nr_rows = 'rows' in self.request and self.request['rows'] or 10
        sord = 'sord' in self.request and self.request['sord'] or 'asc'
        sidx = 'sidx' in self.request and self.request['sidx'] or 'Title'
        rows = []

        # lookup objects from ZODB
        agents = self.bika_setup_catalog(portal_type= 'AetiologicAgent',
                                         inactive_state = 'active')
        if agents and searchTerm:
            agents = [agent for agent in agents if agent.Title.lower().find(searchTerm) > -1
                                                or agent.Description.lower().find(searchTerm) > -1]
        for agent in agents:
            agent = agent.getObject()
            if (len(title) > 0 and agent.Title() == title):
                rows.append({'Title': agent.Title(),
                             'Description': agent.Description(),
                             'AgentUID':agent.UID()})
            elif len(uid) > 0 and agent.UID() == uid:
                rows.append({'Title': agent.Title(),
                             'Description': agent.Description(),
                             'AgentUID':agent.UID()})
            elif len(title)==0 and len(uid)==0:
                rows.append({'Title': agent.Title(),
                             'Description': agent.Description(),
                             'AgentUID':agent.UID()})

        rows = sorted(rows, cmp=lambda x,y: cmp(x.lower(), y.lower()), key=itemgetter(sidx and sidx or 'Title'))
        if sord == 'desc':
            rows.reverse()
        pages = len(rows) / int(nr_rows)
        pages += divmod(len(rows), int(nr_rows))[1] and 1 or 0
        ret = {'page':page,
               'total':pages,
               'records':len(rows),
               'rows':rows[ (int(page) - 1) * int(nr_rows) : int(page) * int(nr_rows) ]}

        return json.dumps(ret)

class ajaxGetAetiologicAgentSubtypes(BrowserView):
    """ Aetologic Agent Subtypes for a specified Aetiologic Agent from site setup
    """
    def __call__(self):
        plone.protect.CheckAuthenticator(self.request)
        title = 'title' in self.request and self.request['title'] or ''
        auid = 'auid' in self.request and self.request['auid'] or ''
        searchTerm = (len(title)==0 and 'searchTerm' in self.request) and self.request['searchTerm'].lower() or title.lower()
        page = 'page' in self.request and self.request['page'] or 1
        nr_rows = 'rows' in self.request and self.request['rows'] or 10
        sord = 'sord' in self.request and self.request['sord'] or 'asc'
        sidx = 'sidx' in self.request and self.request['sidx'] or 'Subtype'
        rows = []

        agents = self.bika_setup_catalog(portal_type='AetiologicAgent', UID=auid)
        if agents and len(agents) == 1:
            agent = agents[0].getObject()
            subtypes = agent.getAetiologicAgentSubtypes()
            if subtypes and searchTerm:
                subtypes = [subtype for subtype in subtypes if subtype['Subtype'].lower().find(searchTerm) > -1]
        
        for subtype in subtypes:
            if (len(title) > 0 and subtype['Subtype'] == title):
                rows.append({'Subtype': subtype['Subtype'],
                         'SubtypeRemarks': subtype.get('SubtypeRemarks', '')})
            elif len(title)==0:
                rows.append({'Subtype': subtype['Subtype'],
                         'SubtypeRemarks': subtype.get('SubtypeRemarks', '')})

        rows = sorted(rows, cmp=lambda x,y: cmp(x.lower(), y.lower()), key=itemgetter(sidx and sidx or 'Subtype'))
        if sord == 'desc':
            rows.reverse()
        pages = len(rows) / int(nr_rows)
        pages += divmod(len(rows), int(nr_rows))[1] and 1 or 0
        ret = {'page':page,
               'total':pages,
               'records':len(rows),
               'rows':rows[ (int(page) - 1) * int(nr_rows) : int(page) * int(nr_rows) ]}

        return json.dumps(ret)

class ajax_rm_provisional(BrowserView):
    def __call__(self):
        plone.protect.CheckAuthenticator(self.request)
        nrs = []
        for nr in json.loads(self.request.get('nrs', "[]")):
            try:
                nrs.append(int(nr))
            except ValueError:
                continue
        if not nrs:
            return
        value = self.context.getProvisionalDiagnosis()
        new = []
        for i,v in enumerate(value):
            if i in nrs:
                continue
            new.append(v)
        self.context.setProvisionalDiagnosis(new)

class ajax_rm_aetiologic(BrowserView):
    def __call__(self):
        plone.protect.CheckAuthenticator(self.request)
        nrs = []
        for nr in json.loads(self.request.get('nrs', "[]")):
            try:
                nrs.append(int(nr))
            except ValueError:
                continue
        if not nrs:
            return
        value = self.context.getAetiologicAgents()
        new = []
        for i,v in enumerate(value):
            if i in nrs:
                continue
            new.append(v)
        self.context.setAetiologicAgents(new)

class ajax_rm_symptoms(BrowserView):
    def __call__(self):
        plone.protect.CheckAuthenticator(self.request)
        nrs = []
        for nr in json.loads(self.request.get('nrs', "[]")):
            try:
                nrs.append(int(nr))
            except ValueError:
                continue
        if not nrs:
            return
        value = self.context.getSymptoms()
        new = []
        for i,v in enumerate(value):
            if i in nrs:
                continue
            new.append(v)
        self.context.setSymptoms(new)

class BatchPublishView(BrowserView):
    """Publish a single Batch.
    """

    template = ViewPageTemplateFile("../browser/templates/batch_publish.pt")

    def __call__(self):

        pc = self.portal_catalog
        bc = self.bika_catalog
        bsc = self.bika_setup_catalog
        self.checkPermission = self.context.portal_membership.checkPermission
        self.now = DateTime()
        self.SamplingWorkflowEnabled = self.context.bika_setup.getSamplingWorkflowEnabled()

        # Client details (if client is associated)
        self.client = None
        client_uid = hasattr(self.context, 'getClientUID') and self.context.getClientUID()
        if client_uid:
            proxies = pc(portal_type='Client', UID=client_uid)
        if proxies:
            self.client = proxies[0].getObject()
            client_address = self.client.getPostalAddress() \
                or self.contact.getBillingAddress() \
                or self.contact.getPhysicalAddress()
            if client_address:
                _keys = ['address', 'city', 'state', 'zip', 'country']
                _list = [client_address.get(v) for v in _keys if client_address.get(v)]
                self.client_address = "<br/>".join(_list).replace("\n", "<br/>")
                if self.client_address.endswith("<br/>"):
                    self.client_address = self.client_address[:-5]
            else:
                self.client_address = None

        # Reporter
        self.member = self.context.portal_membership.getAuthenticatedMember()
        self.username = self.member.getUserName()
        self.reporter = self.user_fullname(self.username)
        self.reporter_email = self.user_email(self.username)
        self.reporter_signature = ""
        c = [x for x in self.bika_setup_catalog(portal_type='LabContact')
             if x.getObject().getUsername() == self.username]
        if c:
            sf = c[0].getObject().getSignature()
            if sf:
                self.reporter_signature = sf.absolute_url() + "/Signature"

        # laboratory
        self.laboratory = self.context.bika_setup.laboratory
        self.accredited = self.laboratory.getLaboratoryAccredited()
        lab_address = self.laboratory.getPrintAddress()
        if lab_address:
            _keys = ['address', 'city', 'state', 'zip', 'country']
            _list = [lab_address.get(v) for v in _keys if lab_address.get(v)]
            self.lab_address = "<br/>".join(_list).replace("\n", "<br/>")
            if self.lab_address.endswith("<br/>"):
                self.lab_address = self.lab_address[:-5]
        else:
            self.lab_address = None

        # Analysis Request results
        self.ars = []
        self.ar_headers = [_("Request ID"),
                           _("Date Requested"),
                           _("Sample Type"),
                           _("Sample Point")]
        self.analysis_headers = [_("Analysis Service"),
                                 _("Method"),
                                 _("Result"),
                                 _("Analyst")]
        for ar in self.context.getAnalysisRequests():
            datecreated = ar.created()
            datereceived = ar.getDateReceived()
            datepublished = ar.getDatePublished()
            datalines = []
            for analysis in ar.getAnalyses(full_objects=True):
                service = analysis.getService()
                method = service.getMethod()
                sample = ar.getSample()
                result = analysis.getResult()
                try:
                    precision = service.getPrecision() and service.getPrecision() or "2"
                    result = float(result)
                    formatted_result = str("%." + precision + "f")%result
                except:
                    precision = "2"
                    formatted_result = result
                datalines.append({_("Analysis Service"): analysis.getService().Title(),
                                  _("Method"): method and method.Title() or "",
                                  _("Result"): formatted_result,
                                  _("Analyst"): self.user_fullname(analysis.getAnalyst())})
            self.ars.append({
                        _("Request ID"): ar.getRequestID(),
                                _("Date Requested"): self.ulocalized_time(datecreated), # requested->created
                        _("Sample Type"): sample.getSampleType() and sample.getSampleType().Title() or '',
                                _("Sample Point"): sample.getSamplePoint() and sample.getSamplePoint().Title() or '',
                        _("datalines"): datalines,
                        })

        # Create Report
        fn = self.context.Title() + " " + self.ulocalized_time(self.now)
        report_html = self.template()

        debug_mode = App.config.getConfiguration().debug_mode
        if debug_mode:
            open(os.path.join(Globals.INSTANCE_HOME,'var', fn + ".html"),
                 "w").write(report_html)

        pisa.showLogging()
        ramdisk = StringIO()
        pdf = pisa.CreatePDF(report_html, ramdisk)
        pdf_data = ramdisk.getvalue()
        ramdisk.close()

        if debug_mode:
            open(os.path.join(Globals.INSTANCE_HOME,'var', fn + ".pdf"),
                 "wb").write(pdf_data)

        # Email to who?

        # Send PDF to browser
        if not pdf.err:
            setheader = self.request.RESPONSE.setHeader
            setheader('Content-Type', 'application/pdf')
            setheader("Content-Disposition", "attachment;filename=\"%s\""%fn)
            self.request.RESPONSE.write(pdf_data)
