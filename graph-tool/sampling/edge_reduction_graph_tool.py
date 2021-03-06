import json
import time
import datetime
from math import log10
from graph_tool.all import *  
import numpy as np
 
def remove_edges(G_reduced, e_delete, items, edges_max_goal):
    current_time = time.time()
    removed_edges = []
    
    sorted_bet_cent_edges_ind = np.argsort(items.a, axis=None)
    sorted_bet_cent_edges_ind = np.unravel_index(np.argsort(items.a, axis=None), items.a.shape)
    sorted_bet_cent_edges = G_reduced.get_edges()[sorted_bet_cent_edges_ind]
    
    goal_num = G_reduced.num_edges() - edges_max_goal
    degrees_ = np.sum([G_reduced.get_in_degrees(G_reduced.get_vertices()), G_reduced.get_out_degrees(G_reduced.get_vertices()) ], axis=0)
        
    for bet_cent in sorted_bet_cent_edges:  
        if (len(removed_edges) >= goal_num): 
            break
            
        if(degrees_[bet_cent[0]] > 2 and degrees_[bet_cent[1]] > 2 ) :
            e_delete[G_reduced.edge(bet_cent[0], bet_cent[1])] = False
            
            G_reduced.set_edge_filter(e_delete)
            degrees_[bet_cent[0]] = degrees_[bet_cent[0]] - 1
            degrees_[bet_cent[1]] = degrees_[bet_cent[1]] - 1

            removed_edges.append(bet_cent) 

    time_spent = time.time()-current_time 
    current_time = time.time()

    return G_reduced, removed_edges
 
def run_edge_reduce(G, bet_cent_edges, edges_max_goal, weight_attr): 
    graph = Graph(G)
    e_delete = graph.new_edge_property("bool", True) 
    G_reduced, removed_edges = remove_edges(graph, e_delete, bet_cent_edges, edges_max_goal) 
    
    G_reduced = postprocess(G, G_reduced, e_delete, removed_edges)

    return G_reduced 

def edge_reduce(G, edges_max_goal, weight_attr): 
    edge_weight = G.edge_properties[weight_attr]
    cent = graph_tool.centrality.betweenness(G, pivots=None, vprop=None, eprop=None, weight=edge_weight, norm=True)
    bet_cent_edges = cent[1] 
    return run_edge_reduce(G, bet_cent_edges, edges_max_goal, weight_attr)
 
def edge_reduce_bc_approximate(G, edges_max_goal, weight_attr): 
    c = 10
    take_count = int(c * log10(G.num_vertices())) 
    nodes_rand = np.random.choice(G.num_vertices(), take_count)
    edge_weight = G.edge_properties[weight_attr]

    cent = graph_tool.centrality.betweenness(G, pivots=G.get_vertices()[nodes_rand], vprop=None, eprop=None, weight=edge_weight, norm=True)
    bet_cent_edges = cent[1] 
    return run_edge_reduce(G, bet_cent_edges, edges_max_goal, weight_attr) 

def get_in_degree(G): 
    return (sum(G.get_in_degrees(G.get_vertices()) )/float(G.num_vertices()))

def get_out_degree(G): 
    return (sum(G.get_out_degrees(G.get_vertices())/float(G.num_vertices())))

def postprocess(G, G_reduced, e_delete, removed_edges): 
    # get disconnected components
    c = label_components(G_reduced, directed=False)[0]
    number_wcc = len(set(c))

    if number_wcc == 1: 
        return G_reduced
  
    current_time = time.time()  
     
    # for each removed edge (sorted highest BC to lowest)
    for edge in reversed(removed_edges):

        # until the graph is connected
        if number_wcc == 1: 
            break
        if c[edge[0]] != c[edge[1]] : 
            # edge is connecting two components  
            original_edge = G.edge(edge[0], edge[1]) 

            # add back the edge 
            e_delete[original_edge] = True 
            G_reduced.set_edge_filter(e_delete)
                
            c = label_components(G_reduced, directed=False)[0]   
        
            number_wcc = len(set(c))  
            break 
 
    return G_reduced  
 
def get_stats(G_reduced, weight_attr, total_weight, in_degree, out_degree, average_clustering, nn, ne, wcc, running_time, time_spent, assortativity):
    edge_weight = G_reduced.edge_properties[weight_attr] 
    t_weight = sum(edge_weight[edge] for edge in G_reduced.edges())

    total_weight.append(t_weight) 
    in_degree.append(get_in_degree(G_reduced))
    out_degree.append(get_out_degree(G_reduced))
    running_time.append(time_spent)
    average_clustering.append(graph_tool.clustering.global_clustering(G_reduced))

    nn.append(G_reduced.num_vertices())
    ne.append(G_reduced.num_edges())
    wcc.append(len(label_components(G_reduced, directed=False)[1])) 
    assortativity.append( graph_tool.correlations.assortativity(G_reduced, "total"))
 
    return total_weight, in_degree, out_degree, average_clustering, nn, ne, wcc, running_time, assortativity

def edge_reduce_approximate_test(G, edge_cuts, weight_attr='transferred'):
    c = 10
    take_count = int(c * log10(G.num_vertices())) 
    nodes_rand = np.random.choice(G.num_vertices(), take_count)
    edge_weight = G.edge_properties[weight_attr]

    cent = graph_tool.centrality.betweenness(G, pivots=G.get_vertices()[nodes_rand], weight=edge_weight)
    bet_cent_edges = cent[1]  

    total_weight = []
    in_degree = []
    out_degree = []
    running_time = []
    average_clustering = []
    nn = []
    ne = []
    wcc = []
    assortativity = []
    graphs = []
    sim = []

    for edge_cut in edge_cuts:  
        current_time = time.time()
        edges_max_goal = G.num_edges() * edge_cut 
        #print("original:", G.num_edges())
        G_reduced = run_edge_reduce(G, bet_cent_edges, edges_max_goal, weight_attr) 

        time_spent = time.time()-current_time 
        total_weight, in_degree, out_degree, average_clustering, nn, ne, wcc, running_time, assortativity = get_stats(G_reduced, weight_attr, total_weight, in_degree, out_degree, average_clustering, nn, ne, wcc, running_time, time_spent, assortativity)

        #print("num edges: ", G_reduced.num_edges())  
        graphs.append(Graph(G_reduced))

        graph_reduced = Graph(G_reduced, prune=True)
        sim.append(graph_tool.topology.similarity(G, graph_reduced))
      
        G.clear_filters() 
        G_reduced.clear_filters() 
    
    print("<<<<<bc sim: ", sim)

    return edge_cuts, total_weight, in_degree, out_degree, average_clustering, nn, ne, wcc, running_time, assortativity

def edge_reduce_approximate_graph(G, edge_cuts, weight_attr='transferred'):
    c = 10
    take_count = int(c * log10(G.num_vertices()))
    nodes_rand = np.random.choice(G.num_vertices(), take_count)
    edge_weight = G.edge_properties[weight_attr]

    graphs = []
    cent = graph_tool.centrality.betweenness(G, pivots=G.get_vertices()[nodes_rand], vprop=None, eprop=None, weight=edge_weight, norm=True)
    bet_cent_edges = cent[1]   

    for edge_cut in edge_cuts:  
        edges_max_goal = G.num_edges() * edge_cut  
        G_reduced = run_edge_reduce(G, bet_cent_edges, edges_max_goal, weight_attr)
        graphs.append(Graph(G_reduced, prune=True)) 

    return graphs
  
def edge_reduce_approximate_test_with_graph(G, edge_cuts, weight_attr='transferred'):
    c = 10
    take_count = int(c * log10(G.num_vertices()))
    nodes_rand = np.random.choice(G.num_vertices(), take_count)
    edge_weight = G.edge_properties[weight_attr]

    cent = graph_tool.centrality.betweenness(G, pivots=G.get_vertices()[nodes_rand], vprop=None, eprop=None, weight=edge_weight, norm=True)
    bet_cent_edges = cent[1]  

    total_weight = []
    in_degree = []
    out_degree = []
    running_time = []
    average_clustering = []
    nn = []
    ne = []
    wcc = []
    running_time = []
    graphs = []
    assortativity= []

    for edge_cut in edge_cuts:  
        current_time = time.time()
        edges_max_goal = G.num_edges() * edge_cut  
        G_reduced = run_edge_reduce(G, bet_cent_edges, edges_max_goal, weight_attr) 

        time_spent = time.time()-current_time 
        total_weight, in_degree, out_degree, average_clustering, nn, ne, wcc, running_time, assortativity = get_stats(G_reduced, weight_attr, total_weight, in_degree, out_degree, average_clustering, nn, ne, wcc, running_time, time_spent, assortativity)
  
        graphs.append(Graph(G_reduced, prune=True)) 

    return edge_cuts, total_weight, in_degree, out_degree, average_clustering, nn, ne, wcc, running_time, graphs

