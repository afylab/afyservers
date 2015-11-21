from __future__ import absolute_import

import collections

from twisted.internet.defer import inlineCallbacks
import twisted.internet.task

from labrad.server import LabradServer, Signal, setting

from . import errors


class DataVault(LabradServer):
    name = 'Data Vault'

    def __init__(self, session_store):
        LabradServer.__init__(self)

        self.session_store = session_store

        # session signals
        self.onNewDir = Signal(543617, 'signal: new dir', 's')
        self.onNewDataset = Signal(543618, 'signal: new dataset', 's')
        self.onTagsUpdated = Signal(543622, 'signal: tags updated', '*(s*s)*(s*s)')

        # dataset signals
        self.onDataAvailable = Signal(543619, 'signal: data available', '')
        self.onNewParameter = Signal(543620, 'signal: new parameter', '')
        self.onCommentsAvailable = Signal(543621, 'signal: comments available', '')

    def initServer(self):
        # create root session
        _root = self.session_store.get([''])

    def contextKey(self, c):
        """The key used to identify a given context for notifications"""
        return c.ID

    def initContext(self, c):
        # start in the root session
        c['path'] = ['']
        # start listening to the root session
        c['session'] = self.session_store.get([''])
        c['session'].listeners.add(self.contextKey(c))

    def expireContext(self, c):
        """Stop sending any signals to this context."""
        key = self.contextKey(c)
        def removeFromList(ls):
            if key in ls:
                ls.remove(key)
        for session in self.session_store.get_all():
            removeFromList(session.listeners)
            for dataset in session.datasets.values():
                removeFromList(dataset.listeners)
                removeFromList(dataset.param_listeners)
                removeFromList(dataset.comment_listeners)

    def getSession(self, c):
        """Get a session object for the current path."""
        return c['session']

    def getDataset(self, c):
        """Get a dataset object for the current dataset."""
        if 'dataset' not in c:
            raise errors.NoDatasetError()
        return c['datasetObj']

    @setting(5, returns=['*s'])
    def dump_existing_sessions(self, c):
        return ['/'.join(session.path)
                for session in self.session_store.get_all()]

    @setting(6, tagFilters=['s', '*s'], includeTags='b',
                returns=['*s{subdirs}, *s{datasets}',
                         '*(s*s){subdirs}, *(s*s){datasets}'])
    def dir(self, c, tagFilters=['-trash'], includeTags=False):
        """Get subdirectories and datasets in the current directory."""
        #print 'dir:', tagFilters, includeTags
        if isinstance(tagFilters, str):
            tagFilters = [tagFilters]
        sess = self.getSession(c)
        dirs, datasets = sess.listContents(tagFilters)
        if includeTags:
            dirs, datasets = sess.getTags(dirs, datasets)
        #print dirs, datasets
        return dirs, datasets

    @setting(7, path=['{get current directory}',
                      's{change into this directory}',
                      '*s{change into each directory in sequence}',
                      'w{go up by this many directories}'],
                create='b',
                returns='*s')
    def cd(self, c, path=None, create=False):
        """Change the current directory.

        The empty string '' refers to the root directory. If the 'create' flag
        is set to true, new directories will be created as needed.
        Returns the path to the new current directory.
        """
        if path is None:
            return c['path']

        temp = c['path'][:] # copy the current path
        if isinstance(path, (int, long)):
            if path > 0:
                temp = temp[:-path]
                if not len(temp):
                    temp = ['']
        else:
            if isinstance(path, str):
                path = [path]
            for segment in path:
                if segment == '':
                    temp = ['']
                else:
                    temp.append(segment)
                if not self.session_store.exists(temp) and not create:
                    raise errors.DirectoryNotFoundError(temp)
                _session = self.session_store.get(temp) # touch the session
        if c['path'] != temp:
            # stop listening to old session and start listening to new session
            key = self.contextKey(c)
            c['session'].listeners.remove(key)
            session = self.session_store.get(temp)
            session.listeners.add(key)
            c['session'] = session
            c['path'] = temp
        return c['path']

    @setting(8, name='s', returns='*s')
    def mkdir(self, c, name):
        """Make a new sub-directory in the current directory.

        The current directory remains selected.  You must use the
        'cd' command to select the newly-created directory.
        Directory name cannot be empty.  Returns the path to the
        created directory.
        """
        if name == '':
            raise errors.EmptyNameError()
        path = c['path'] + [name]
        if self.session_store.exists(path):
            raise errors.DirectoryExistsError(path)
        _sess = self.session_store.get(path) # make the new directory
        return path

    @setting(9, name='s',
                independents=['*s', '*(ss)'],
                dependents=['*s', '*(sss)'],
                returns='(*s{path}, s{name})')
    def new(self, c, name, independents, dependents):
        """Create a new Dataset.

        Independent and dependent variables can be specified either
        as clusters of strings, or as single strings.  Independent
        variables have the form (label, units) or 'label [units]'.
        Dependent variables have the form (label, legend, units)
        or 'label (legend) [units]'.  Label is meant to be an
        axis label that can be shared among traces, while legend is
        a legend entry that should be unique for each trace.
        Returns the path and name for this dataset.
        """
        session = self.getSession(c)
        dataset = session.newDataset(name or 'untitled', independents, dependents)
        c['dataset'] = dataset.name # not the same as name; has number prefixed
        c['datasetObj'] = dataset
        c['filepos'] = 0 # start at the beginning
        c['commentpos'] = 0
        c['writing'] = True
        return c['path'], c['dataset']

    @setting(10, name=['s', 'w'], returns='(*s{path}, s{name})')
    def open(self, c, name):
        """Open a Dataset for reading.

        You can specify the dataset by name or number.
        Returns the path and name for this dataset.
        """
        session = self.getSession(c)
        dataset = session.openDataset(name)
        c['dataset'] = dataset.name # not the same as name; has number prefixed
        c['datasetObj'] = dataset
        c['filepos'] = 0
        c['commentpos'] = 0
        c['writing'] = False
        key = self.contextKey(c)
        dataset.keepStreaming(key, 0)
        dataset.keepStreamingComments(key, 0)
        return c['path'], c['dataset']

    @setting(20, data=['*v: add one row of data',
                       '*2v: add multiple rows of data'],
                 returns='')
    def add(self, c, data):
        """Add data to the current dataset.

        The number of elements in each row of data must be equal
        to the total number of variables in the data set
        (independents + dependents).
        """
        dataset = self.getDataset(c)
        if not c['writing']:
            raise errors.ReadOnlyError()
        dataset.addData(data)

    @setting(21, limit='w', startOver='b', returns='*2v')
    def get(self, c, limit=None, startOver=False):
        """Get data from the current dataset.

        Limit is the maximum number of rows of data to return, with
        the default being to return the whole dataset.  Setting the
        startOver flag to true will return data starting at the beginning
        of the dataset.  By default, only new data that has not been seen
        in this context is returned.
        """
        dataset = self.getDataset(c)
        c['filepos'] = 0 if startOver else c['filepos']
        data, c['filepos'] = dataset.getData(limit, c['filepos'])
        key = self.contextKey(c)
        dataset.keepStreaming(key, c['filepos'])
        return data

    @setting(100, returns='(*(ss){independents}, *(sss){dependents})')
    def variables(self, c):
        """Get the independent and dependent variables for the current dataset.

        Each independent variable is a cluster of (label, units).
        Each dependent variable is a cluster of (label, legend, units).
        Label is meant to be an axis label, which may be shared among several
        traces, while legend is unique to each trace.
        """
        ds = self.getDataset(c)
        ind = [(i['label'], i['units']) for i in ds.independents]
        dep = [(d['category'], d['label'], d['units']) for d in ds.dependents]
        return ind, dep

    @setting(120, returns='*s')
    def parameters(self, c):
        """Get a list of parameter names."""
        dataset = self.getDataset(c)
        key = self.contextKey(c)
        dataset.param_listeners.add(key) # send a message when new parameters are added
        return [par['label'] for par in dataset.parameters]

    @setting(121, 'add parameter', name='s', returns='')
    def add_parameter(self, c, name, data):
        """Add a new parameter to the current dataset."""
        dataset = self.getDataset(c)
        dataset.addParameter(name, data)

    @setting(124, 'add parameters', params='?{((s?)(s?)...)}', returns='')
    def add_parameters(self, c, params):
        """Add a new parameter to the current dataset."""
        dataset = self.getDataset(c)
        dataset.addParameters(params)


    @setting(126, 'get name', returns='s')
    def get_name(self, c):
        """Get the name of the current dataset."""
        dataset = self.getDataset(c)
        name = dataset.name
        return name

    @setting(122, 'get parameter', name='s')
    def get_parameter(self, c, name, case_sensitive=True):
        """Get the value of a parameter."""
        dataset = self.getDataset(c)
        return dataset.getParameter(name, case_sensitive)

    @setting(123, 'get parameters')
    def get_parameters(self, c):
        """Get all parameters.

        Returns a cluster of (name, value) clusters, one for each parameter.
        If the set has no parameters, nothing is returned (since empty clusters
        are not allowed).
        """
        dataset = self.getDataset(c)
        names = [par['label'] for par in dataset.parameters]
        params = tuple((name, dataset.getParameter(name)) for name in names)
        key = self.contextKey(c)
        dataset.param_listeners.add(key) # send a message when new parameters are added
        if len(params):
            return params

    @setting(200, 'add comment', comment=['s'], user=['s'], returns=[''])
    def add_comment(self, c, comment, user='anonymous'):
        """Add a comment to the current dataset."""
        dataset = self.getDataset(c)
        return dataset.addComment(user, comment)

    @setting(201, 'get comments', limit=['w'], startOver=['b'],
                                  returns=['*(t, s{user}, s{comment})'])
    def get_comments(self, c, limit=None, startOver=False):
        """Get comments for the current dataset."""
        dataset = self.getDataset(c)
        c['commentpos'] = 0 if startOver else c['commentpos']
        comments, c['commentpos'] = dataset.getComments(limit, c['commentpos'])
        key = self.contextKey(c)
        dataset.keepStreamingComments(key, c['commentpos'])
        return comments

    @setting(300, 'update tags', tags=['s', '*s'],
                  dirs=['s', '*s'], datasets=['s', '*s'],
                  returns='')
    def update_tags(self, c, tags, dirs, datasets=None):
        """Update the tags for the specified directories and datasets.

        If a tag begins with a minus sign '-' then the tag (everything
        after the minus sign) will be removed.  If a tag begins with '^'
        then it will be toggled from its current state for each entry
        in the list.  Otherwise it will be added.

        The directories and datasets must be in the current directory.
        """
        if isinstance(tags, str):
            tags = [tags]
        if isinstance(dirs, str):
            dirs = [dirs]
        if datasets is None:
            datasets = [self.getDataset(c)]
        elif isinstance(datasets, str):
            datasets = [datasets]
        sess = self.getSession(c)
        sess.updateTags(tags, dirs, datasets)

    @setting(301, 'get tags',
                  dirs=['s', '*s'], datasets=['s', '*s'],
                  returns='*(s*s)*(s*s)')
    def get_tags(self, c, dirs, datasets):
        """Get tags for directories and datasets in the current dir."""
        sess = self.getSession(c)
        if isinstance(dirs, str):
            dirs = [dirs]
        if isinstance(datasets, str):
            datasets = [datasets]
        return sess.getTags(dirs, datasets)


class DataVaultMultiHead(DataVault):
    """Data Vault server with additional settings for running multi-headed.

    One instance will be created for each manager we connect to, and new
    instances will be created when we reconnect after losing a connection.
    """

    def __init__(self, host, port, password, hub, session_store):
        DataVault.__init__(self, session_store)
        self.host = host
        self.port = port
        self.password = password
        self.hub = hub
        self.alive = False

    def initServer(self):
        DataVault.initServer(self)
        # let the DataVaultHost know that we connected
        self.hub.connect(self)
        self.alive = True
        self.keepalive_timer = twisted.internet.task.LoopingCall(self.keepalive)
        self.onShutdown().addBoth(self.end_keepalive)
        self.keepalive_timer.start(120)

    def end_keepalive(self, *ignored):
        # stopServer is only called when the whole application shuts down.
        # We need to manually use the onShutdown() callback
        self.keepalive_timer.stop()

    @inlineCallbacks
    def keepalive(self):
        print "sending keepalive to {}:{}".format(self.host, self.port)
        try:
            yield self.client.manager.echo('ping')
        except:
            pass # We don't care about errors, dropped connections will be recognized automatically

    def contextKey(self, c):
        return ExtendedContext(self, c.ID)

    @setting(401, 'get servers', returns='*(swb)')
    def get_servers(self, c):
        """
        Returns the list of running servers as tuples of (host, port, connected?)
        """
        rv = []
        for s in self.hub:
            host = s.host
            port = s.port
            running = hasattr(s, 'server') and bool(s.server.alive)
            print "host: %s port: %s running: %s" % (host, port, running)
            rv.append((host, port, running))
        return rv

    @setting(402, 'add server', host='s', port='w', password='s')
    def add_server(self, c, host, port=None, password=None):
        """
        Add new server to the list.
        """
        port = port if port is not None else self.port
        password = password if password is not None else self.password
        self.hub.add_server(host, port, password)

    @setting(403, 'Ping Managers')
    def ping_managers(self, c):
        self.hub.ping()

    @setting(404, 'Kick Managers', host_regex='s', port='w')
    def kick_managers(self, c, host_regex, port=0):
        self.hub.kick(host_regex, port)

    @setting(405, 'Reconnect', host_regex='s', port='w')
    def reconnect(self, c, host_regex, port=0):
        self.hub.reconnect(host_regex, port)

    @setting(406, 'Refresh Managers')
    def refresh_managers(self, c):
        return self.hub.refresh_managers()

class ExtendedContext(object):
    '''
    This is an extended context that contains the manager.  This prevents
    multiple contexts with the same client ID from conflicting if they are
    connected to different managers.
    '''
    def __init__(self, server, ctx):
        self.__server = server
        self.__ctx = ctx

    @property
    def server(self):
        return self.__server

    @property
    def context(self):
        return self.__ctx

    def __eq__(self, other):
        return (self.context == other.context) and (self.server == other.server)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.context) ^ hash(self.server.host) ^ self.server.port
