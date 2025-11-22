export function Footer() {
  return (
    <footer className="border-t">
      <div className="container px-4 sm:px-6 lg:px-8 py-6 text-sm text-stone-600 flex items-center justify-between">
        <p>© {new Date().getFullYear()} Spoon Rebalancer</p>
        <p>
          <a href="/accessibility" className="underline">Accessibility</a> ·
          <a href="/styleguide" className="underline ml-2">Style Guide</a>
        </p>
      </div>
    </footer>
  )
}