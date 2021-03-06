# Assignment 4.1
# DENCLUE Algorithm
# Autazhor: Saurabh Biswas
# DSC550 T302

# I have taken the sample code from github as a reference and then modified as
# per my need. Original author of the sample code is mgarrett.
# link : https://github.com/mgarrett57/DENCLUE/blob/master/denclue.py

# import required libraries
import numpy as np
from sklearn.base import BaseEstimator, ClusterMixin
import networkx as nx
import sys
import pandas as pd


def file_read(filename):
    """ This routine reads file into a dataframe"""
    df1 = pd.read_csv(filename, header=None)
    return df1


def _hill_climb(x_t, X, W=None, h=0.1, eps=1e-7):
    """
    This function climbs the 'hill' of the kernel density function
    and finds the 'peak', which represents the density attractor
    """
    error = 99.
    prob = 0.
    x_l1 = np.copy(x_t)

    # Sum of the last three steps is used to establish radius
    # of neighborhood around attractor. Authors suggested two
    # steps works well, but I found three is more robust to
    # noisey datasets.
    radius_new = 0.
    radius_old = 0.
    radius_twiceold = 0.
    iters = 0.
    while True:
        radius_thriceold = radius_twiceold
        radius_twiceold = radius_old
        radius_old = radius_new
        x_l0 = np.copy(x_l1)
        x_l1, density = _step(x_l0, X, W=W, h=h)
        error = density - prob
        prob = density
        radius_new = np.linalg.norm(x_l1 - x_l0)
        radius = radius_thriceold + radius_twiceold + radius_old + radius_new
        iters += 1
        if iters > 3 and error < eps:
            break
    return [x_l1, prob, radius]


def _step(x_l0, X, W=None, h=0.1):
    n = X.shape[0]
    d = X.shape[1]
    superweight = 0.  # superweight is the kernel X weight for each item
    x_l1 = np.zeros((1, d))
    if W is None:
        W = np.ones((n, 1))
    else:
        W = W
    for j in range(n):
        kernel = kernelize(x_l0, X[j], h, d)
        kernel = kernel * W[j] / (h ** d)
        superweight = superweight + kernel
        x_l1 = x_l1 + (kernel * X[j])
    x_l1 = x_l1 / superweight
    density = superweight / np.sum(W)
    return [x_l1, density]


def kernelize(x, y, h, degree):
    kernel = np.exp(-(np.linalg.norm(x - y) / h) ** 2. / 2.) / ((2. * np.pi) ** (degree / 2))
    return kernel


class DENCLUE(BaseEstimator, ClusterMixin):
    """Perform DENCLUE clustering from vector array.
    Parameters
    ----------
    h : float, optional
        The smoothing parameter for the gaussian kernel. This is a hyper-
        parameter, and the optimal value depends on data. Default is the
        np.std(X)/5.
    eps : float, optional
        Convergence threshold parameter for density attractors
    min_density : float, optional
        The minimum kernel density required for a cluster attractor to be
        considered a cluster and not noise.  Cluster info will stil be kept
        but the label for the corresponding instances will be -1 for noise.
        Since what consitutes a high enough kernel density depends on the
        nature of the data, it's often best to fit the model first and
        explore the results before deciding on the min_density, which can be
        set later with the 'set_minimum_density' method.
        Default is 0.
    metric : string, or callable
        The metric to use when calculating distance between instances in a
        feature array. In this version, I've only tested 'euclidean' at this
        moment.
    Attributes
    -------
    cluster_info_ : dictionary [n_clusters]
        Contains relevant information of all clusters (i.e. density attractors)
        Information is retained even if the attractor is lower than the
        minimum density required to be labelled a cluster.
    labels_ : array [n_samples]
        Cluster labels for each point.  Noisy samples are given the label -1.
    Notes
    -----
    References
    ----------
    Hinneburg A., Gabriel HH. "DENCLUE 2.0: Fast Clustering Based on Kernel
    Density Estimation". In: R. Berthold M., Shawe-Taylor J., Lavrač N. (eds)
    Advances in Intelligent Data Analysis VII. IDA 2007
    """

    def __init__(self, h=None, eps=1e-8, min_density=0., metric='euclidean'):
        self.h = h
        self.eps = eps
        self.min_density = min_density
        self.metric = metric

    def fit(self, X, y=None, sample_weight=None):
        if not self.eps > 0.0:
            raise ValueError("eps must be positive.")
        self.n_samples = X.shape[0]
        self.n_features = X.shape[1]
        density_attractors = np.zeros((self.n_samples, self.n_features))
        radii = np.zeros((self.n_samples, 1))
        density = np.zeros((self.n_samples, 1))

        # create default values
        if self.h is None:
            self.h = np.std(X) / 5
        if sample_weight is None:
            sample_weight = np.ones((self.n_samples, 1))
        else:
            sample_weight = sample_weight

        # initialize all labels to noise
        labels = -np.ones(X.shape[0])

        # climb each hill
        for i in range(self.n_samples):
            density_attractors[i], density[i], radii[i] = _hill_climb(X[i], X, W=sample_weight,
                                                                      h=self.h, eps=self.eps)

        # initialize cluster graph to finalize clusters. Networkx graph is
        # used to verify clusters, which are connected components of the
        # graph. Edges are defined as density attractors being in the same
        # neighborhood as defined by our radii for each attractor.
        cluster_info = {}
        num_clusters = 0
        cluster_info[num_clusters] = {'instances': [0],
                                      'centroid': np.atleast_2d(density_attractors[0])}
        g_clusters = nx.Graph()
        for j1 in range(self.n_samples):
            g_clusters.add_node(j1)
            g_clusters.nodes[j1]['attractor'] = density_attractors[j1]
            g_clusters.nodes[j1]['radius'] = radii[j1]
            g_clusters.nodes[j1]['density'] = density[j1]

        # populate cluster graph
        # no support for Graph.node in latest networkx version. So chaged it to Graph.nodes
        for j1 in range(self.n_samples):
            for j2 in (x for x in range(self.n_samples) if x != j1):
                if g_clusters.has_edge(j1, j2):
                    continue
                diff = np.linalg.norm(g_clusters.nodes[j1]['attractor'] - g_clusters.nodes[j2]['attractor'])
                if diff <= (g_clusters.nodes[j1]['radius'] + g_clusters.nodes[j1]['radius']):
                    g_clusters.add_edge(j1, j2)

        # connected components represent a cluster
        num_clusters = 0

        # loop through all connected components
        for c in nx.connected_components(g_clusters):
            clust = g_clusters.subgraph(c)

            # get maximum density of attractors and location
            max_instance = max(clust, key=lambda x: clust.nodes[x]['density'])
            max_density = clust.nodes[max_instance]['density']
            max_centroid = clust.nodes[max_instance]['attractor']

            # In Hinneberg, Gabriel (2007), for attractors in a component that
            # are not fully connected (i.e. not all attractors are within each
            # other's neighborhood), they recommend re-running the hill climb
            # with lower eps. From testing, this seems unnecesarry for all but
            # special edge cases. Therefore, completeness info is put into
            # cluster info dict, but not used to re-run hill climb.
            complete = False
            c_size = len(clust.nodes())
            if clust.number_of_edges() == (c_size * (c_size - 1)) / 2.:
                complete = True

            # populate cluster_info dict
            cluster_info[num_clusters] = {'instances': clust.nodes(),
                                          'size': c_size,
                                          'centroid': max_centroid,
                                          'density': max_density,
                                          'complete': complete}

            # if the cluster density is not higher than the minimum,
            # instances are kept classified as noise
            if max_density >= self.min_density:
                labels[clust.nodes()] = num_clusters
            num_clusters += 1

        self.clust_info_ = cluster_info
        self.labels_ = labels
        return self.clust_info_     # return cluster info

    def get_density(self, x, X, y=None, sample_weight=None):
        superweight = 0.
        n_samples = X.shape[0]
        n_features = X.shape[1]
        if sample_weight is None:
            sample_weight = np.ones((n_samples, 1))
        else:
            sample_weight = sample_weight
        for y in range(n_samples):
            kernel = kernelize(x, X[y], h=self.h, degree=n_features)
            kernel = kernel * sample_weight[y] / (self.h ** n_features)
            superweight = superweight + kernel
        density = superweight / np.sum(sample_weight)
        return density

    def set_minimum_density(self, min_density):
        self.min_density = min_density
        labels_copy = np.copy(self.labels_)
        for k in self.clust_info_.keys():
            if self.clust_info_[k]['density'] < min_density:
                labels_copy[self.clust_info_[k]['instances']] = -1
            else:
                labels_copy[self.clust_info_[k]['instances']] = k
        self.labels_ = labels_copy
        return self


if __name__ == '__main__':

    # Check if the command line arguments are given
    if len(sys.argv) < 4:
        print('no/less arguments passed')
        sys.exit()

    print('Filename: ', sys.argv[1])
    print('Epsilon Value: ', sys.argv[2])
    print('Minimum Density: ', sys.argv[3])

    filename = (sys.argv[1])

    try:
        eps = float(sys.argv[2])
    except ValueError:
        print('Enter a float value')
        sys.exit()

    try:
        min_dnesity = float(sys.argv[3])
    except ValueError:
        print('Enter a float value')
        sys.exit()

    # read and prepare data
    df1 = file_read(filename)   # read file
    data = np.array(df1)        # convert it into numpy array
    iris = np.mat(data[:, 0:4])     # create a matrix for first 4 columns

    denclue = DENCLUE(h=0.37, eps=eps, min_density=min_dnesity, metric='euclidean')
    clusters = denclue.fit(iris, y=None, sample_weight=None)

    # print(clusters)
    # load into dataframe, dictionary keys should be loaded into dataframe row.
    df2 = pd.DataFrame.from_dict(clusters, orient='index')
    row, col = df2.shape
    # print(df2.columns)
    df3 = df2['size']
    print('Number of cluster is:', row)
    print('Size of each cluster:\n', df3)

    df3 = df2[['density', 'instances']]
    print('Density attractor and point assignment of each cluster are:\n', df3, '\n')

    df3 = df2['instances']  # get only data points
    array = df3.to_numpy()  # convert it into numpy

    dict_dummy = {}
    i = 0
    for x in array:     # run a loop to extract points and its cluster assignment into a dictionary
        for j in x:
            dict_dummy[j] = i
        i += 1
    dict_dummy = dict(sorted(dict_dummy.items()))    # sort on keys
    df3 = pd.DataFrame.from_dict(dict_dummy, orient='index')

    # concatenate cluster with original datarame
    df3 = pd.concat([df1, df3], axis=1, ignore_index=True)
    df3.columns = ['attr1', 'attr2', 'attr3', 'attr4', 'type', 'cluster']  # assign column name
    df3 = df3.assign(New=1)  # add a new column with constant value
    df3 = df3.groupby(['type', 'cluster'], as_index=False)['New'].sum()

    # get max count from confusion matrix
    cnt_1 = df3[df3.type == 'Iris-setosa'].New.max()
    cnt_2 = df3[df3.type == 'Iris-versicolor'].New.max()
    cnt_3 = df3[df3.type == 'Iris-virginica'].New.max()
    purity = (cnt_1 + cnt_2 + cnt_3) / df3.New.sum()
    print('\n The purity value is:{:.2f}'.format(purity))

