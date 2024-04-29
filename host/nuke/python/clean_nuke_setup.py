# Keep Openpype Instances and all their dependencies
# and remove everything else.
# some functions are copied and adopted from
#   https://github.com/seaniedan/nuketools by Sean Danischevsky 2014


import nuke
from openpype.hosts.nuke.api.pipeline import list_instances


def upstream(nodes):
    if not nodes:
        return []

    dependencies = nuke.dependencies(
        nodes,
        nuke.EXPRESSIONS|nuke.INPUTS|nuke.HIDDEN_INPUTS
    )
    for dependency in dependencies:
        nodes.extend(upstream([dependency]))

    return nodes


def select_upstream_sd(nodes):
    """ select all upstream nodes (dependencies) of given nodes
        and optionally backdrops if the nodes are on backdrops
    """
    if not nodes:
        return

    #recursive dependencies (upstream nodes)
    nodes+= upstream(nodes)

    #add backdrops:
    for bd in nuke.allNodes("BackdropNode"):
        bd_nodes = bd.getNodes()
        for node in nodes:
            if node in bd_nodes:
                nodes.append(bd)
                break

    #remove any duplicates
    nodes= list(set(nodes))

    #select them
    for node in nodes:
        node.setSelected(True)

    #return the list
    return nodes


def cleanupScript():
    instances = list_instances()
    nodes =  [i[0] for i in instances]
    if not nodes:
        nodes = nuke.selectedNodes()
    if not nodes:
        print("Operation Failed. No selected nodes found.")
        return

    upstream_nodes = select_upstream_sd(nodes)
    delete_list= [
        node for node in nuke.allNodes()
        if node not in upstream_nodes and node.Class() != "Viewer"
    ]

    # delete nodes we do not need anymore
    for node in delete_list:
        nuke.delete(node)