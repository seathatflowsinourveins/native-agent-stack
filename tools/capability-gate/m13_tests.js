// Rows for m13.yaml (promptfoo 0.123.1 dynamic test generation, site/docs/configuration/test-cases.md "Dynamic Test
// Generation"). Each repetition is one row per tree, tree a first, and each row runs on its own arm's provider for that
// tree (test-level `providers`, same page, "Filtering Tests by Provider"). Repetition ids are unique across arms, so
// every row's files sit at their own .cg/<rep>/ path.
const ARMS = [
  { arm: 'gate', first: 1, reps: 20 },
  { arm: 'ctrl-disabled', first: 21, reps: 3 },
  { arm: 'ctrl-wrongroot', first: 24, reps: 3 },
];

module.exports = async function () {
  const tests = [];
  for (const { arm, first, reps } of ARMS) {
    for (let index = first; index < first + reps; index += 1) {
      const rep = `r${String(index).padStart(2, '0')}`;
      for (const tree of ['a', 'b']) {
        tests.push({ description: `${arm} ${rep} ${tree}`, providers: [`${arm}-${tree}`], vars: { arm, rep, tree } });
      }
    }
  }
  return tests;
};
