import bpy, time
from bpy.app.handlers import persistent
from mn_utils import *



compiledCodeObjects = []

def updateAnimationTrees(treeChanged = True):
	if treeChanged:
		rebuildNodeNetworks()
	for codeObject in compiledCodeObjects:
		exec(codeObject)
		try: exec(codeObject)
		except: 
			rebuildNodeNetworks()
			try: exec(codeObject)
			except BaseException as e: print(e)
			
			
# compile code objects
################################
		
def rebuildNodeNetworks():
	global compiledCodeObjects
	compiledCodeObjects = []
	nodeNetworks = getNodeNetworks()
	for network in nodeNetworks:
		codeString = getCodeStringToExecuteNetwork(network)
		compiledCodeObjects.append(compile(codeString, "<string>", "exec"))
		
def getCodeStringToExecuteNetwork(network):
	orderedNodes = orderNodes(network)
	setUniqueCodeIndexToEveryNode(orderedNodes)
	codeLines = []
	codeLines.append("nodes = bpy.data.node_groups['" + network[0].id_data.name + "'].nodes")
	for node in orderedNodes:
		if isExecuteableNode(node):
			codeLines.append(getNodeDeclarationString(node))
			codeLines.append(getNodeExecutionString(node))
	codeString = "\n".join(codeLines)
	return codeString
	
def setUniqueCodeIndexToEveryNode(nodes):
	for i, node in enumerate(nodes):
		node.codeIndex = i
def isExecuteableNode(node):
	return hasattr(node, "execute")
def getNodeDeclarationString(node):
	return getNodeVariableName(node) + " = nodes['"+node.name+"']"
def getNodeExecutionString(node):
	return getNodeOutputName(node) + " = " + getNodeVariableName(node) + ".execute(" + generateInputListString(node) + ")"
		
def generateInputListString(node):
	inputParts = []
	for socket in node.inputs:
		originSocket = getOriginSocket(socket)
		if isOtherOriginSocket(socket, originSocket):
			otherNode = originSocket.node
			part = "'" + socket.identifier + "' : " + getNodeOutputName(otherNode) + "['" + originSocket.identifier + "']"
		else:
			part = "'" + socket.identifier + "' : " + getNodeVariableName(node) + ".inputs['" + socket.identifier + "'].getValue()"
		inputParts.append(part)
	return "{ " + ", ".join(inputParts) + " }"
		
def getNodeVariableName(node):
	return "node_" + str(node.codeIndex)
def getNodeOutputName(node):
	return "output_" + str(node.codeIndex)
		

# get node networks (groups of connected nodes)
###############################################
		
def getNodeNetworks():
	nodeNetworks = []
	nodeTrees = getAnimationNodeTrees()
	for nodeTree in nodeTrees:
		nodeNetworks.extend(getNodeNetworksFromTree(nodeTree))
	return nodeNetworks
	
def getAnimationNodeTrees():
	nodeTrees = []
	for nodeTree in bpy.data.node_groups:
		if hasattr(nodeTree, "isAnimationNodeTree"):
			nodeTrees.append(nodeTree)
	return nodeTrees
		
def getNodeNetworksFromTree(nodeTree):
	nodes = nodeTree.nodes
	resetNodeFoundAttributes(nodes)
	
	networks = []
	for node in nodes:
		if not node.isFound:
			networks.append(getNodeNetworkFromNode(node))
	return networks
	
def getNodeNetworkFromNode(node):
	nodesToCheck = [node]
	network = [node]
	node.isFound = True
	while len(nodesToCheck) > 0:
		linkedNodes = []
		for node in nodesToCheck:
			linkedNodes.extend(getLinkedButNotFoundNodes(node))
		network.extend(linkedNodes)
		setNodesAsFound(linkedNodes)
		nodesToCheck = linkedNodes
	return network
	
def setNodesAsFound(nodes):
	for node in nodes: node.isFound = True
	
def getLinkedButNotFoundNodes(node):
	nodes = []
	for socket in node.inputs:
		for link in socket.links:
			nodes.append(link.from_node)
	for socket in node.outputs:
		for link in socket.links:
			nodes.append(link.to_node)
	nodes = sortOutAlreadyFoundNodes(nodes)
	return nodes
	
def sortOutAlreadyFoundNodes(nodes):
	return [node for node in nodes if not node.isFound]
	

# order nodes (network) to possible execution sequence
######################################################
	
def orderNodes(nodes):
	resetNodeFoundAttributes(nodes)
	orderedNodeList = []
	for node in nodes:
		if not node.isFound:
			orderedNodeList.extend(getAllNodeDependencies(node))
			orderedNodeList.append(node)
			node.isFound = True
	return orderedNodeList

def getAllNodeDependencies(node):
	dependencies = []
	directDependencies = getNotFoundDirectDependencies(node)
	for directDependency in directDependencies:
		dependencies.extend(getAllNodeDependencies(directDependency))
	dependencies.extend(directDependencies)
	return dependencies
	
def getNotFoundDirectDependencies(node):
	directDependencies = []
	for socket in node.inputs:
		if hasLinks(socket):
			node = socket.links[0].from_node
			if not node.isFound:
				node.isFound = True
				directDependencies.append(node)
	return directDependencies
	
def resetNodeFoundAttributes(nodes):
	for node in nodes: node.isFound = False
		
	
bpy.types.Node.isFound = bpy.props.BoolProperty(default = False)
bpy.types.Node.codeIndex = bpy.props.IntProperty()

		
		
# Force Cache Rebuilding Panel
##############################
		
class AnimationNodesPanel(bpy.types.Panel):
	bl_idname = "mn.panel"
	bl_label = "Animation Nodes"
	bl_space_type = "NODE_EDITOR"
	bl_region_type = "UI"
	bl_context = "objectmode"
	
	@classmethod
	def poll(self, context):
		return len(getAnimationNodeTrees()) > 0
	
	def draw(self, context):
		layout = self.layout
		layout.operator("mn.force_full_update")
		scene = context.scene
		layout.label("Update when:")
		layout.prop(scene, "updateAnimationTreeOnFrameChange", text = "Frames Changes")
		layout.prop(scene, "updateAnimationTreeOnSceneUpdate", text = "Scene Updates")
		layout.prop(scene, "updateAnimationTreeOnPropertyChange", text = "Property Changes")
		
		
		
class ForceNodeTreeUpdate(bpy.types.Operator):
	bl_idname = "mn.force_full_update"
	bl_label = "Force Node Tree Update"

	def execute(self, context):
		updateAnimationTrees(treeChanged = True)
		return {'FINISHED'}
	
	
		
# handlers to start the update
##############################

bpy.types.Scene.updateAnimationTreeOnFrameChange = bpy.props.BoolProperty(default = True, name = "Update Animation Tree On Frame Change")
bpy.types.Scene.updateAnimationTreeOnSceneUpdate = bpy.props.BoolProperty(default = True, name = "Update Animation Tree On Scene Update")
bpy.types.Scene.updateAnimationTreeOnPropertyChange = bpy.props.BoolProperty(default = True, name = "Update Animation Tree On Property Change")
	
@persistent
def frameChangeHandler(scene):
	if scene.updateAnimationTreeOnFrameChange:
		updateAnimationTrees(False)
@persistent
def sceneUpdateHandler(scene):
	if scene.updateAnimationTreeOnSceneUpdate:
		updateAnimationTrees(False)
@persistent
def fileLoadHandler(scene):
	updateAnimationTrees(True)
def nodePropertyChanged(self, context):
	if context.scene.updateAnimationTreeOnPropertyChange:
		updateAnimationTrees(False)
def nodeTreeChanged():
	updateAnimationTrees(True)

	
bpy.app.handlers.frame_change_post.append(frameChangeHandler)
bpy.app.handlers.scene_update_post.append(sceneUpdateHandler)
bpy.app.handlers.load_post.append(fileLoadHandler)
		
		
# register
################################
		
def register():
	bpy.utils.register_module(__name__)

def unregister():
	bpy.utils.unregister_module(__name__)