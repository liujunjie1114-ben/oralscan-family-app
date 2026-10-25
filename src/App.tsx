// Preview host: renders the standalone single-file app from public/oralscan.html.
export default function App() {
  return (
    <iframe
      src="/oralscan.html"
      title="OralScan · Tooth Hero Parent App"
      style={{ display: 'block', width: '100%', height: '100dvh', border: 0, background: '#fff' }}
    />
  )
}
