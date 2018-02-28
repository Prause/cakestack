# cake.py lib
- TODO `start_command`: combine `tag_run_dir/'working'` to not pollute the `tag_run_dir`
- TODO `start_command`: create `w_dir` if it doesn't exist

# autocake
- TODO: autocake should fulfill expectations e.g.:
-- expectation from cakeloader that a certain version is running)
-- expectations arising from config changes (e.g. working dir/command)
-- later: expectations from cakecloud
- TODO: autocake restarts services that don't fulfill expectations

# cakeloader
- TODO: cakeloader loads the most recent version of any tag in the config that has a git repository configured.
- it communicates this new version as an expectation to autocake -> how?
