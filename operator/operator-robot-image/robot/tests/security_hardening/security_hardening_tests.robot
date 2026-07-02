# Copyright 2024-2025 NetCracker Technology Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

*** Settings ***
Library    PlatformLibrary    managed_by_operator=%{RABBIT_IS_MANAGED_BY_OPERATOR}

*** Test Cases ***
Test Container Hardening
    [Tags]    rabbitmq    hardening
    ${part_of}=    Create List    %{PART_OF}
    ${exclusions}=    Create Dictionary    _all=CH12
    Check Container Hardening    ${part_of}    %{NAMESPACE}    ${exclusions}
