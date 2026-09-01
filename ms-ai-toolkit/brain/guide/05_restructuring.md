You may change this schema at any time - that is explicitly sanctioned. When you do:
  1. ALTER/CREATE in one transaction,
  2. bump meta.schema_version,
  3. append what changed and why to guide topic 06_changelog,
  4. update 02_query_recipes if the query shape changed,
  5. run: bash @SCRIPTS@/brain-check.sh
Bias to fewer tables. A table nobody has written to in a month should be dropped.

BOUNDED BY DESIGN (three unbounded accumulators were found here in one day):
  * guide topic 06_changelog - trim past ~5k chars; promote durable lessons to 09_lessons.
    It reached 33k chars and 82% of the whole guide before anyone looked.
  * @HOME@/capture.d, delivered.d, collide.d - the hooks self-prune to 400 markers.
  * health table - ~16 rows/day forever:
      DELETE FROM health WHERE day < date('now','-180 day');
None of these break at scale, which is exactly why none of them would ever be noticed.

The guide topics 00-05 and 09 are seeded from @SCRIPTS@/guide/*.md by brain-init.py. Edit the
FILE, not the row, or a package update overwrites your change. Topics you create at runtime
(06_changelog, 08_current_advice) have no file and are never overwritten.
