export default function NotFound() {
  return (
    <div className="container py-12">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="text-sm text-stone-600">The requested resource does not exist.</p>
      <a href="/" className="underline">Go to Dashboard</a>
    </div>
  )
}