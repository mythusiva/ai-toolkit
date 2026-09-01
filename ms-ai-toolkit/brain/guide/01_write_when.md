Write a row the moment one of these happens - not at end of task, you will forget:
  * You proved something about runtime behaviour        -> fact (evidence is MANDATORY)
  * You finally found where a symbol lives              -> code_map
  * Something surprised you and cost >2 tool calls      -> gotcha
  * A command worked after fiddling with env/flags/cwd  -> recipe
  * A fork got resolved (by user or by evidence)        -> decision, INCLUDING the rejected options
  * You start or finish a unit of work                  -> work_log
  * An inbound item you chose NOT to act on             -> thread, state='declined' + verdict

Never write a claim you have not checked. If unproven, insert it with status='hypothesis'.

The helper fills in line numbers and git blob shas and parameterises every value, so quotes and
apostrophes in your text cannot break the SQL:
  python3 @SCRIPTS@/brain-note.py map <repo> <path> <symbol|-> "<what it does + what surprised you>"
  python3 @SCRIPTS@/brain-note.py gotcha <scope> "<trigger>" "<symptom>" "<fix>"
  python3 @SCRIPTS@/brain-note.py recipe <name> <scope> "<goal>" "<command>"
  python3 @SCRIPTS@/brain-note.py fact <scope> <subject> "<claim>" "<evidence>"
  python3 @SCRIPTS@/brain-note.py claim <scope> "<task>"    # before you touch a branch

`map` is the one everyone skips and the one that pays: orientation is the largest measured cost
and code_map is what removes it. If you hunted for something and found it, that is a map row.
