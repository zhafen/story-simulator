import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { Position } from '../api'
import './WorldView.css'

const WIDTH = 640
const HEIGHT = 520
const PADDING = 40

interface Props {
  positions: Position[]
}

function padExtent([min, max]: [number, number]): [number, number] {
  if (min === max) return [min - 1, max + 1]
  const pad = (max - min) * 0.15
  return [min - pad, max + pad]
}

export function WorldView({ positions }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    const svg = d3.select(svgRef.current)

    const xExtent = d3.extent(positions, (d) => d.x) as [number, number]
    const yExtent = d3.extent(positions, (d) => d.y) as [number, number]
    const xDomain = padExtent(xExtent[0] === undefined ? [-1, 1] : xExtent)
    const yDomain = padExtent(yExtent[0] === undefined ? [-1, 1] : yExtent)

    const xScale = d3.scaleLinear().domain(xDomain).range([PADDING, WIDTH - PADDING])
    const yScale = d3.scaleLinear().domain(yDomain).range([HEIGHT - PADDING, PADDING])

    const nodes = svg
      .select<SVGGElement>('.nodes')
      .selectAll<SVGGElement, Position>('g.node')
      .data(positions, (d) => d.alias)

    const entered = nodes.enter().append('g').attr('class', 'node')
    entered.append('circle').attr('r', 5)
    entered.append('text').attr('dx', 8).attr('dy', 4)

    nodes.exit().remove()

    entered
      .merge(nodes)
      .attr('transform', (d) => `translate(${xScale(d.x)}, ${yScale(d.y)})`)
      .select('text')
      .text((d) => d.alias)
  }, [positions])

  return (
    <svg ref={svgRef} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="world-view">
      <g className="nodes" />
    </svg>
  )
}
