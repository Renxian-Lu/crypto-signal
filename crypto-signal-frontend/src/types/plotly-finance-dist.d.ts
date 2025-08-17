declare module 'plotly.js-finance-dist' {
  import type { PlotlyHTMLElement, Config, Layout, Data } from 'plotly.js'

  export function newPlot(
    root: string | HTMLElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<PlotlyHTMLElement>

  export function react(
    root: string | HTMLElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<PlotlyHTMLElement>

  export function redraw(root: string | HTMLElement): void
  export function relayout(root: string | HTMLElement, layout: Partial<Layout>): Promise<PlotlyHTMLElement>
  export function restyle(root: string | HTMLElement, style: any, traces?: number[]): Promise<PlotlyHTMLElement>
  export function purge(root: string | HTMLElement): void

  const Plotly: any
  export default Plotly
}
