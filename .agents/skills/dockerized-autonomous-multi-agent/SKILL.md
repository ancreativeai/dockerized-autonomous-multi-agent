```markdown
# dockerized-autonomous-multi-agent Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches best practices and conventions for contributing to the `dockerized-autonomous-multi-agent` TypeScript repository. The codebase focuses on building autonomous multi-agent systems that are containerized using Docker, emphasizing modularity and maintainability without relying on a specific framework.

## Coding Conventions

### File Naming
- Use **kebab-case** for all file names.
  - Example:  
    ```
    agent-manager.ts
    docker-utils.ts
    ```

### Import Style
- Use **relative imports** for internal modules.
  - Example:
    ```typescript
    import { Agent } from './agent';
    import { startDocker } from '../utils/docker-utils';
    ```

### Export Style
- Prefer **named exports** over default exports.
  - Example:
    ```typescript
    // agent.ts
    export interface Agent { ... }
    export function createAgent() { ... }
    ```

### Commit Messages
- No strict prefixing; commit messages are freeform but concise (average ~58 characters).
  - Example:
    ```
    Add agent initialization logic and update Docker config
    ```

## Workflows

### Adding a New Agent Module
**Trigger:** When implementing a new agent type.
**Command:** `/add-agent-module`

1. Create a new file in `src/agents/` using kebab-case (e.g., `explorer-agent.ts`).
2. Define the agent logic using named exports.
3. Import and register the agent in the main agent manager.
4. Write corresponding tests in a file named `explorer-agent.test.ts`.

### Running Tests
**Trigger:** To verify code correctness after changes.
**Command:** `/run-tests`

1. Ensure all test files follow the `*.test.*` pattern.
2. Use the project's test runner (framework unknown; check package scripts or documentation).
3. Run the test command (e.g., `npm test` or `yarn test`).
4. Review output and fix any failing tests.

### Refactoring Utilities
**Trigger:** When updating shared utility functions.
**Command:** `/refactor-utils`

1. Locate the relevant utility file (e.g., `docker-utils.ts`).
2. Make changes using named exports.
3. Update all relative imports in dependent modules.
4. Run tests to ensure no regressions.

## Testing Patterns

- Test files are named using the `*.test.*` pattern (e.g., `agent-manager.test.ts`).
- The specific testing framework is not detected; check the project documentation or `package.json` for details.
- Tests should cover both positive and negative cases for each module.
- Place test files alongside the modules they test or in a dedicated `tests/` directory.

  ```typescript
  // agent-manager.test.ts
  import { createAgent } from './agent-manager';

  describe('createAgent', () => {
    it('should initialize agent with correct properties', () => {
      const agent = createAgent('explorer');
      expect(agent.type).toBe('explorer');
    });
  });
  ```

## Commands
| Command            | Purpose                                      |
|--------------------|----------------------------------------------|
| /add-agent-module  | Scaffold and register a new agent module     |
| /run-tests         | Execute all test suites                      |
| /refactor-utils    | Refactor utility functions and update imports|
```