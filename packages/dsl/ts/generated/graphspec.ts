/* AUTO-GENERATED from packages/dsl (Pydantic). DO NOT EDIT — run `pnpm --filter @calypr/dsl gen`. */

/**
 * How concurrent/iterative writes to a state channel merge (LangGraph reducer).
 */
export type Reducer = "append" | "last";

/**
 * A complete agent graph as drawn on the canvas.
 */
export interface GraphSpec {
  description?: string;
  edges?: EdgeSpec[];
  entry?: string | null;
  id: string;
  name: string;
  nodes?: NodeSpec[];
  schema_version?: string;
  state?: StateChannel[];
}
/**
 * A directed control-flow edge. `condition` is set on edges leaving a Router.
 */
export interface EdgeSpec {
  condition?: string | null;
  id: string;
  source: string;
  target: string;
}
/**
 * A vertex in the control-flow graph. `type` resolves to a node-registry entry.
 */
export interface NodeSpec {
  config?: {
    [k: string]: unknown;
  };
  id: string;
  position?: {
    [k: string]: number;
  } | null;
  type: string;
}
/**
 * One typed variable in the shared graph state.
 */
export interface StateChannel {
  default?: unknown;
  key: string;
  reducer?: Reducer;
  type?: string;
}
