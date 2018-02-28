# cakestack
kubernetes + jenkins for the poor, lonely and lazy

## scope
cakestack is an ecosystem of tools that allow userland deployment & orchestration of services (todo: put deployment and orchestration in quotation marks).

If you ever caught yourself running a serivce in `screen` just to keep it running in the background as your user and being able to have a look at the logs every now and then: this is for you!

## vision
On the long run, cakestack might also have kind of a "cloud mode" (now really quoation marks!) that allows doing the above but not caring about which machine actually runs the service. This way it might be used as a stack for deploying services of a bunch of e.g. raspberry pi -> hence the name.

For current ideas, consult your friendly TODO.md file.

## usage
`cake start --tag your_tag`

## config
The config is in yaml format with the first level key being the service's tag and second-level keys:
- entry: the entrypoint (i.e. command to be started)
- dir: the working directory to start the command in
- auto: shall this command be auto-started. only works with a running autocake (consider running autocake as a cakestack-service
- git: (TODO) git repo to be pulled, will be used as working dir. only works with cakeloader running regularly (consider making it a service that is autocaked)
- frequency: (TODO) someting like run once every n minutes...? not sure yet

See also the `example_config.yaml` file

The config file has to reside in the `CAKESTACK_DIR`: `$HOME/.cakestack/`.

## disclaimer
Yo, don't expect backwards compatibility. Or reliability. Or in fact anything whatsoever.

## license
Whatever floats your boat. (license might change)
