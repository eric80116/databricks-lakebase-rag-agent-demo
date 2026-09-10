import React from 'react'

interface Suggestion {
  text: string
  lang: string
}

interface SuggestionCardsProps {
  suggestions: Suggestion[]
  onSelect: (text: string) => void
}

const SuggestionCards: React.FC<SuggestionCardsProps> = ({
  suggestions,
  onSelect,
}) => {
  return (
    <div className="suggestions-container">
      {suggestions.map((suggestion, idx) => (
        <button
          key={idx}
          className="suggestion-card"
          onClick={() => onSelect(suggestion.text)}
          title={suggestion.text}
        >
          {suggestion.text}
        </button>
      ))}
    </div>
  )
}

export default SuggestionCards
