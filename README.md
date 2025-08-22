# sdk-to-mcp-converter
sdk to mcp converter
any sdk should theoretically be able to be converted in its entirety with an appropriate setup. specify include_methods under appropriate operation_groups to set up specific methods. set discover: auto to add all available methods in the sdk.

STEPS
write the yaml file (see examples)
Done

EXAMPLES
config.yaml - sets up kubernetes with a select set of methods 
	(openai doesn't let you have more than 128 tools at once so I added this functionality to be able to actually use the product)

config_azure.yaml - introduces the operations_groups key, which can be infinitely nested as appropriate (the program will serialize and deserialize recursively as needed)

config_github.yaml - supports the default desired behavior in the project spec (add all available methods) using discover: auto
