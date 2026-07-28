import type { ReactNode } from 'react'

const URL_REGEX = /((?:https?:\/\/|www\.)[^\s<]+)/gi
const TRAILING_PUNCTUATION = /[.,;:!?)\]}'"]+$/

export function linkifyText(text: string): ReactNode {
  if (!text) return text
  const parts = text.split(URL_REGEX)
  return parts.map((part, i) => {
    // text.split() con una regex a un solo gruppo intercala i match catturati
    // agli indici dispari: non serve ritestare la regex per capire cos'e' cosa.
    if (i % 2 === 0) return part

    const trailingMatch = part.match(TRAILING_PUNCTUATION)
    const trailing = trailingMatch ? trailingMatch[0] : ''
    const url = trailing ? part.slice(0, -trailing.length) : part
    const href = url.toLowerCase().startsWith('www.') ? `https://${url}` : url

    return (
      <span key={i}>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-primary underline hover:no-underline break-all"
        >
          {url}
        </a>
        {trailing}
      </span>
    )
  })
}
