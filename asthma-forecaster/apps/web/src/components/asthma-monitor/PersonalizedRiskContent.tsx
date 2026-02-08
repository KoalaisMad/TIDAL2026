"use client"

import * as React from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useRouter } from "next/navigation"

interface PersonalizedData {
  name: string
  heightFeet: string
  heightInches: string
  weight: string
  smokerExposure: "smoker" | "exposed" | "none" | ""
  petExposure: "yes" | "no" | ""
}

interface FormErrors {
  name?: string
  height?: string
  weight?: string
  smokerExposure?: string
  petExposure?: string
}

export function PersonalizedRiskContent() {
  const router = useRouter()
  const [formData, setFormData] = React.useState<PersonalizedData>({
    name: "",
    heightFeet: "",
    heightInches: "",
    weight: "",
    smokerExposure: "",
    petExposure: "",
  })
  const [errors, setErrors] = React.useState<FormErrors>({})
  const [touched, setTouched] = React.useState<Record<string, boolean>>({})

  const validateHeight = (): string | undefined => {
    const feet = formData.heightFeet
    const inches = formData.heightInches

    if (!feet && !inches) {
      return "Height is required"
    }
    if (!feet) {
      return "Please enter feet"
    }
    if (!inches) {
      return "Please enter inches"
    }

    const feetNum = parseFloat(feet)
    const inchesNum = parseFloat(inches)

    if (isNaN(feetNum) || isNaN(inchesNum)) {
      return "Please enter valid numbers"
    }
    if (!Number.isInteger(feetNum)) {
      return "Feet must be a whole number"
    }
    if (feetNum < 2 || feetNum > 8) {
      return "Height must be between 2' and 8'"
    }
    if (inchesNum < 0 || inchesNum >= 12) {
      return "Inches must be between 0 and 11"
    }
    if (feetNum < 2 && inchesNum < 0) {
      return "Height seems too short (minimum 2' 0\")"
    }

    return undefined
  }

  const validateField = (field: keyof PersonalizedData | "height", value?: string): string | undefined => {
    if (field === "height") {
      return validateHeight()
    }

    switch (field) {
      case "name":
        const nameVal = value ?? formData.name
        if (!nameVal.trim()) {
          return "Name is required"
        }
        if (nameVal.trim().length < 2) {
          return "Name must be at least 2 characters"
        }
        if (nameVal.trim().length > 50) {
          return "Name must be less than 50 characters"
        }
        break

      case "weight":
        const weightVal = value ?? formData.weight
        if (!weightVal) {
          return "Weight is required"
        }
        const weight = parseFloat(weightVal)
        if (isNaN(weight)) {
          return "Weight must be a valid number"
        }
        if (weight < 10 || weight > 1000) {
          return "Weight must be between 10 and 1000 lbs"
        }
        break

      case "smokerExposure":
        const smokerVal = value ?? formData.smokerExposure
        if (!smokerVal) {
          return "Please select a smoking exposure option"
        }
        break

      case "petExposure":
        const petVal = value ?? formData.petExposure
        if (!petVal) {
          return "Please select a pet exposure option"
        }
        break
    }
    return undefined
  }

  const handleInputChange = (field: keyof PersonalizedData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    
    // Clear height error when either height field changes
    if (field === "heightFeet" || field === "heightInches") {
      if (errors.height) {
        setErrors((prev) => ({ ...prev, height: undefined }))
      }
    } else {
      // Clear error when user starts typing
      if (errors[field as keyof FormErrors]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }))
      }
    }
  }

  const handleBlur = (field: keyof PersonalizedData | "height") => {
    setTouched((prev) => ({ ...prev, [field]: true }))
    const error = validateField(field)
    
    // For height fields, set the error on the "height" key
    if (field === "heightFeet" || field === "heightInches") {
      setErrors((prev) => ({ ...prev, height: error }))
    } else {
      setErrors((prev) => ({ ...prev, [field]: error }))
    }
  }

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {}
    let isValid = true

    // Validate name
    const nameError = validateField("name")
    if (nameError) {
      newErrors.name = nameError
      isValid = false
    }

    // Validate height (as one field)
    const heightError = validateHeight()
    if (heightError) {
      newErrors.height = heightError
      isValid = false
    }

    // Validate weight
    const weightError = validateField("weight")
    if (weightError) {
      newErrors.weight = weightError
      isValid = false
    }

    // Validate smoking exposure
    const smokerError = validateField("smokerExposure")
    if (smokerError) {
      newErrors.smokerExposure = smokerError
      isValid = false
    }

    // Validate pet exposure
    const petError = validateField("petExposure")
    if (petError) {
      newErrors.petExposure = petError
      isValid = false
    }

    setErrors(newErrors)
    setTouched({
      name: true,
      height: true,
      heightFeet: true,
      heightInches: true,
      weight: true,
      smokerExposure: true,
      petExposure: true,
    })

    return isValid
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (validateForm()) {
      // TODO: Process form data and calculate personalized risk
      const formattedHeight = `${formData.heightFeet}' ${formData.heightInches}"`
      console.log("Form submitted:", {
        ...formData,
        formattedHeight,
      })
    } else {
      console.log("Form has validation errors")
    }
  }

  return (
    <>
      <Card className="p-8">
        <div className="space-y-6">
          <h2 className="text-2xl font-bold">Personalized Risk Assessment</h2>
          <p className="text-base text-muted-foreground leading-relaxed">
            Enter your personal health information to receive a customized asthma risk assessment.
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Name Field */}
            <div className="space-y-2">
              <label htmlFor="name" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                Name <span className="text-red-500">*</span>
              </label>
              <Input
                id="name"
                type="text"
                placeholder="Enter your name"
                value={formData.name}
                onChange={(e) => handleInputChange("name", e.target.value)}
                onBlur={() => handleBlur("name")}
                className={`bg-white ${touched.name && errors.name ? "border-red-500 focus-visible:ring-red-500" : ""}`}
              />
              {touched.name && errors.name && (
                <p className="text-sm text-red-500">{errors.name}</p>
              )}
            </div>

            {/* Height and Weight Fields */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              {/* Height Field - Unified Input */}
              <div className="space-y-2">
                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                  Height <span className="text-red-500">*</span>
                </label>
                <div className={`flex h-12 items-center gap-1 rounded-3xl border-0 bg-white px-5 py-3 text-base shadow-md transition-all ${
                  (touched.heightFeet || touched.heightInches) && errors.height 
                    ? "ring-2 ring-red-500/50 shadow-lg" 
                    : "focus-within:ring-2 focus-within:ring-ring focus-within:shadow-lg"
                }`}>
                  <input
                    id="heightFeet"
                    type="number"
                    placeholder="5"
                    value={formData.heightFeet}
                    onChange={(e) => handleInputChange("heightFeet", e.target.value)}
                    onBlur={() => handleBlur("heightFeet")}
                    min="2"
                    max="8"
                    step="1"
                    className="w-14 bg-transparent text-center outline-none placeholder:text-muted-foreground/60 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                  <span className="text-sm text-muted-foreground/60">ft</span>
                  <input
                    id="heightInches"
                    type="number"
                    placeholder="6"
                    value={formData.heightInches}
                    onChange={(e) => handleInputChange("heightInches", e.target.value)}
                    onBlur={() => handleBlur("heightInches")}
                    min="0"
                    max="11"
                    step="0.5"
                    className="w-14 bg-transparent text-center outline-none placeholder:text-muted-foreground/60 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                  <span className="text-sm text-muted-foreground/60">in</span>
                </div>
                {(touched.heightFeet || touched.heightInches) && errors.height && (
                  <p className="text-sm text-red-500">{errors.height}</p>
                )}
              </div>

              {/* Weight Field */}
              <div className="space-y-2">
                <label htmlFor="weight" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                  Weight <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <Input
                    id="weight"
                    type="number"
                    placeholder="150"
                    value={formData.weight}
                    onChange={(e) => handleInputChange("weight", e.target.value)}
                    onBlur={() => handleBlur("weight")}
                    min="10"
                    max="1000"
                    step="0.1"
                    className={`bg-white pr-12 ${touched.weight && errors.weight ? "border-red-500 focus-visible:ring-red-500" : ""}`}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground pointer-events-none">
                    lbs
                  </span>
                </div>
                {touched.weight && errors.weight && (
                  <p className="text-sm text-red-500">{errors.weight}</p>
                )}
              </div>
            </div>

            {/* Smoker Exposure Field */}
            <div className="space-y-3">
              <label className="text-sm font-medium leading-none">
                Smoking Exposure <span className="text-red-500">*</span>
              </label>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <input
                    type="radio"
                    id="smoker"
                    name="smokerExposure"
                    value="smoker"
                    checked={formData.smokerExposure === "smoker"}
                    onChange={(e) => handleInputChange("smokerExposure", e.target.value)}
                    className="h-4 w-4 border-gray-300 text-primary focus:ring-2 focus:ring-primary"
                  />
                  <label htmlFor="smoker" className="text-sm font-normal cursor-pointer">
                    I am a smoker
                  </label>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="radio"
                    id="exposed"
                    name="smokerExposure"
                    value="exposed"
                    checked={formData.smokerExposure === "exposed"}
                    onChange={(e) => handleInputChange("smokerExposure", e.target.value)}
                    className="h-4 w-4 border-gray-300 text-primary focus:ring-2 focus:ring-primary"
                  />
                  <label htmlFor="exposed" className="text-sm font-normal cursor-pointer">
                    I am often around smokers
                  </label>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="radio"
                    id="none"
                    name="smokerExposure"
                    value="none"
                    checked={formData.smokerExposure === "none"}
                    onChange={(e) => handleInputChange("smokerExposure", e.target.value)}
                    className="h-4 w-4 border-gray-300 text-primary focus:ring-2 focus:ring-primary"
                  />
                  <label htmlFor="none" className="text-sm font-normal cursor-pointer">
                    No smoking exposure
                  </label>
                </div>
              </div>
              {touched.smokerExposure && errors.smokerExposure && (
                <p className="text-sm text-red-500">{errors.smokerExposure}</p>
              )}
            </div>

            {/* Pet Exposure Field */}
            <div className="space-y-3">
              <label className="text-sm font-medium leading-none">
                Pet Exposure <span className="text-red-500">*</span>
              </label>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <input
                    type="radio"
                    id="pet-yes"
                    name="petExposure"
                    value="yes"
                    checked={formData.petExposure === "yes"}
                    onChange={(e) => handleInputChange("petExposure", e.target.value)}
                    className="h-4 w-4 border-gray-300 text-primary focus:ring-2 focus:ring-primary"
                  />
                  <label htmlFor="pet-yes" className="text-sm font-normal cursor-pointer">
                    Yes, I have pets or am regularly around pets
                  </label>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="radio"
                    id="pet-no"
                    name="petExposure"
                    value="no"
                    checked={formData.petExposure === "no"}
                    onChange={(e) => handleInputChange("petExposure", e.target.value)}
                    className="h-4 w-4 border-gray-300 text-primary focus:ring-2 focus:ring-primary"
                  />
                  <label htmlFor="pet-no" className="text-sm font-normal cursor-pointer">
                    No pet exposure
                  </label>
                </div>
              </div>
              {touched.petExposure && errors.petExposure && (
                <p className="text-sm text-red-500">{errors.petExposure}</p>
              )}
            </div>

            {/* Submit Button */}
            <div className="pt-4">
              <Button type="submit" className="w-full sm:w-auto sm:px-12">
                Calculate My Risk
              </Button>
            </div>
          </form>
        </div>
      </Card>

      <div className="sticky bottom-6 flex justify-center pt-4 md:static">
        <Button
          size="pill"
          variant="outline"
          className="w-full md:w-fit md:px-12"
          onClick={() => {
            router.push("/breathe-well/environmental")
          }}
        >
          Back to Environmental Risk
        </Button>
      </div>
    </>
  )
}
