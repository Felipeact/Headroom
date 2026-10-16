# context

The product and planning documents for Headroom. Start here if you're new to the project.

## Read in this order

1. [project-overview.md](project-overview.md): the problem, the product, who it's for, and how it differs from competitors.
2. [Roadmap.md](Roadmap.md): the milestones, the pilot gate, the architecture at each stage, and the decision log.
3. [DESIGN.md](DESIGN.md): the design system, the writing guidelines, and the list of mockups in [design/mockups/](../design/mockups/).
4. [specs/](specs/): the work itself.

## Specs

v1 is split into 36 short specs, numbered in build order (`01-setup-frontend.md` to `36-launch-pilot.md`). Each one is a small piece of work that can be finished and reviewed in a day or two.

Each spec file has:

- **Status:** Not started, In progress, or Done
- **Depends on:** the specs that must be Done before it can start
- **Done when:** the checks that must pass, each backed by a test or a repeatable check

The rules for working through specs:

- Set the status to In progress before you write any code, and to Done only once every "Done when" item passes.
- Build only what the spec calls for.
- A spec that adds or changes a screen is finished only after the screen has been checked in the running app: loading, empty, and error states, a 375-pixel-wide layout, and keyboard-only use.

The spec names start with an area: `setup`, `web`, `api`, `accounts`, `bank`, `forecast`, `alerts`, `email`, or `launch`.

### Later

[specs/later/](specs/later/) holds the features that wait until the first clients confirm the product: billing, QuickBooks and Xero, scenarios, one-click actions, a workspace for accounting firms, and more. Don't build anything from it without asking first. Its [README](specs/later/README.md) explains how it's organized.

## Other folders

- [token-usage/](token-usage/): a log of how many tokens AI agents used per feature.

## Changing these documents

`DESIGN.md` and the mockups in `design/` are shared design files. Change them only in a separate commit, and ask first.
