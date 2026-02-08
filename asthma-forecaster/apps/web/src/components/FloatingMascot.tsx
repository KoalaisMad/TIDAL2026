'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'

export default function FloatingMascot() {
  const [position, setPosition] = useState({ x: 20, y: 20 })
  const [animationDuration, setAnimationDuration] = useState(15)

  useEffect(() => {
    // Randomize starting position
    setPosition({
      x: Math.random() * 80 + 10, // 10-90% of viewport width
      y: Math.random() * 80 + 10, // 10-90% of viewport height
    })
    setAnimationDuration(Math.random() * 10 + 12) // 12-22 seconds
  }, [])

  const handleClick = () => {
    // Move to a nearby position when clicked (small jump away)
    const jumpDistance = 15 // percentage of viewport
    const angle = Math.random() * 2 * Math.PI // random direction
    
    let newX = position.x + Math.cos(angle) * jumpDistance
    let newY = position.y + Math.sin(angle) * jumpDistance
    
    // Keep within bounds (5-95% of viewport)
    newX = Math.max(5, Math.min(95, newX))
    newY = Math.max(5, Math.min(95, newY))
    
    setPosition({ x: newX, y: newY })
  }

  return (
    <div
      className="floating-mascot cursor-pointer"
      onClick={handleClick}
      style={{
        position: 'fixed',
        left: `${position.x}%`,
        top: `${position.y}%`,
        zIndex: 9999,
        width: '150px',
        height: '150px',
        animationDuration: `${animationDuration}s`,
        transition: 'left 0.8s cubic-bezier(0.34, 1.56, 0.64, 1), top 0.8s cubic-bezier(0.34, 1.56, 0.64, 1)',
      }}
    >
      <Image
        src="/chiky.svg"
        alt="Mascot"
        width={150}
        height={150}
        className="drop-shadow-lg"
        priority
      />
      <style jsx>{`
        @keyframes float {
          0%, 100% {
            transform: translate(0, 0) rotate(0deg);
          }
          25% {
            transform: translate(30px, -40px) rotate(5deg);
          }
          50% {
            transform: translate(-20px, -60px) rotate(-5deg);
          }
          75% {
            transform: translate(-40px, -30px) rotate(3deg);
          }
        }

        .floating-mascot {
          animation: float linear infinite;
          will-change: transform;
        }

        @media (prefers-reduced-motion: reduce) {
          .floating-mascot {
            animation: none;
          }
        }
      `}</style>
    </div>
  )
}
