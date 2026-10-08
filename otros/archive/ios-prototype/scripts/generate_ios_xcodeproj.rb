#!/usr/bin/env ruby

require "fileutils"
require "xcodeproj"

root = File.expand_path("..", __dir__)
ios_root = File.join(root, "ios")
project_dir = File.join(ios_root, "HandWashComplianceApp")
project_path = File.join(project_dir, "HandWashCompliance.xcodeproj")
source_root = File.join(ios_root, "HandWashCompliance", "HandWashCompliance")

FileUtils.mkdir_p(project_dir)
FileUtils.rm_rf(project_path) if File.exist?(project_path)

project = Xcodeproj::Project.new(project_path)
project.root_object.attributes["LastUpgradeCheck"] = "2700"
project.root_object.compatibility_version = "Xcode 16.0"

target = project.new_target(:application, "HandWashCompliance", :ios, "16.0")
target.product_name = "HandWashCompliance"

project_group = project.main_group
app_group = project_group.new_group("HandWashCompliance", source_root)

swift_files = Dir[File.join(source_root, "**", "*.swift")].sort
swift_files.each do |path|
  ref = app_group.new_file(path)
  target.add_file_references([ref])
end

info_plist = File.join(source_root, "Info.plist")
target.build_configurations.each do |config|
  config.build_settings["PRODUCT_BUNDLE_IDENTIFIER"] = "com.handwash.compliance"
  config.build_settings["SWIFT_VERSION"] = "5.0"
  config.build_settings["IPHONEOS_DEPLOYMENT_TARGET"] = "16.0"
  config.build_settings["INFOPLIST_FILE"] = "$(SRCROOT)/../HandWashCompliance/HandWashCompliance/Info.plist"
  config.build_settings["TARGETED_DEVICE_FAMILY"] = "1,2"
  config.build_settings["CODE_SIGN_STYLE"] = "Automatic"
  config.build_settings["GENERATE_INFOPLIST_FILE"] = "NO"
end

package = project.new(Xcodeproj::Project::Object::XCRemoteSwiftPackageReference)
package.repositoryURL = "https://github.com/ultralytics/yolo-ios-app.git"
package.requirement = { "kind" => "upToNextMajorVersion", "minimumVersion" => "8.9.13" }
project.root_object.package_references << package

product = project.new(Xcodeproj::Project::Object::XCSwiftPackageProductDependency)
product.product_name = "UltralyticsYOLO"
product.package = package
target.package_product_dependencies << product

project.save
puts "Generated #{project_path} with #{swift_files.length} Swift files"
