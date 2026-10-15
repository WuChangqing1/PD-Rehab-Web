/** One coordinate system shared by keyboard and overlay. SVG uses width=700. */
export const keyCenterX = (index: number, width: number) => (index + .5) * width / 7
export const staffY = (index: number) => 48 + 12 * Math.sin(index * Math.PI / 3)
