```markdown
# dockerized-autonomous-multi-agent Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and workflows used in the `dockerized-autonomous-multi-agent` TypeScript codebase. You will learn the project's coding conventions, file organization, import/export styles, and how to work with its test structure. This guide is ideal for contributors who want to maintain consistency and efficiency when developing or reviewing code in this repository.

## Coding Conventions

### File Naming
- Use **camelCase** for file names.
  - Example: `agentManager.ts`, `taskScheduler.ts`

### Imports
- Use **relative imports** for referencing modules within the project.
  - Example:
    ```typescript
    import { Agent } from './agent';
    import { TaskScheduler } from '../utils/taskScheduler';
    ```

### Exports
- Use **named exports** for all modules.
  - Example:
    ```typescript
    // agentManager.ts
    export function createAgent(config: AgentConfig) { ... }
    export const AGENT_STATUS = { ... };
    ```

### General Code Style
- TypeScript is the primary language.
- No framework is detected; the codebase is likely modular and framework-agnostic.
- Commit messages are freeform, with no enforced prefix or structure.

## Workflows

### Adding a New Agent Module
**Trigger:** When you need to implement a new type of autonomous agent.
**Command:** `/add-agent-module`

1. Create a new file in camelCase (e.g., `newAgent.ts`).
2. Implement the agent logic using TypeScript.
3. Use named exports for all functions and constants.
4. Import dependencies using relative paths.
5. Add or update relevant tests in a corresponding `.test.ts` file.

### Running Tests
**Trigger:** When you want to verify code correctness.
**Command:** `/run-tests`

1. Identify test files matching the pattern `*.test.*`.
2. Use the project's test runner (framework unknown; check documentation or package.json).
3. Run all tests and ensure they pass before merging or deploying changes.

### Refactoring Existing Modules
**Trigger:** When improving or restructuring code for clarity or efficiency.
**Command:** `/refactor-module`

1. Rename files using camelCase if necessary.
2. Update import paths to remain relative.
3. Ensure all exports are named.
4. Update or add tests to cover the refactored code.

## Testing Patterns

- Test files follow the pattern `*.test.*` (e.g., `agentManager.test.ts`).
- The testing framework is not explicitly detected; check for configuration in the repository.
- Place test files alongside or near the modules they test.
- Example test file structure:
  ```typescript
  // agentManager.test.ts
  import { createAgent } from './agentManager';

  describe('createAgent', () => {
    it('should initialize agent with correct config', () => {
      // test implementation
    });
  });
  ```

## Commands
| Command           | Purpose                                               |
|-------------------|-------------------------------------------------------|
| /add-agent-module | Scaffold and implement a new agent module             |
| /run-tests        | Execute all test files in the repository              |
| /refactor-module  | Refactor an existing module following conventions     |
```
